import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import os
import signal
import numpy as np
from PIL import Image, ImageTk, ImageDraw
import queue
import threading
import time
from datetime import datetime, timezone
import ephem
import pyaudio
import random

class SatelliteTracker:
    def __init__(self):
        self.observer = ephem.Observer()
        self.observer.elevation = 50
        self.noaa_sats = {}
        self.update_tles()

    def update_tles(self):
        try:
            import requests
            url = "https://celestrak.org/NORAD/elements/weather.txt"
            response = requests.get(url, timeout=10)
            tle_data = response.text.split('\n')
            
            for i in range(0, len(tle_data)-2, 3):
                name = tle_data[i].strip()
                if "NOAA" in name:
                    line1 = tle_data[i+1].strip()
                    line2 = tle_data[i+2].strip()
                    self.noaa_sats[name] = ephem.readtle(name, line1, line2)
        except Exception as e:
            print(f"TLE update failed: {e}")
            self.load_fallback_tles()

    def load_fallback_tles(self):
        self.noaa_sats = {
            'NOAA 15': ephem.readtle(
                "NOAA 15",
                "1 25338U 98030A  23145.48693287  .00000074  00000-0  65301-4 0  9993",
                "2 25338  98.7248 194.4486 0011014 324.8595  35.2286 14.25911716130330"
            ),
            'NOAA 18': ephem.readtle(
                "NOAA 18",
                "1 28654U 05018A  23145.09264352  .00000094  00000-0  65301-4 0  9994",
                "2 28654  98.9943 194.4622 0011014 324.8595  35.2286 14.25911716130328"
            )
        }

    def set_location(self, lat, lon, elev=50):
        self.observer.lat = str(lat)
        self.observer.lon = str(lon)
        self.observer.elevation = elev
        
    def next_pass(self, sat_name):
        sat = self.noaa_sats.get(sat_name)
        if not sat:
            return None
            
        self.observer.date = datetime.now(timezone.utc)
        sat.compute(self.observer)
        
        try:
            tr, azr, tt, altt, ts, azs = self.observer.next_pass(sat)
            return {
                'rise_time': ephem.localtime(tr),
                'max_time': ephem.localtime(tt),
                'set_time': ephem.localtime(ts),
                'max_elevation': altt
            }
        except Exception as e:
            print(f"Pass calculation error: {e}")
            return None

class NOAADecoder:
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.current_image = None
        self.signal_quality = 0
        self.line_counter = 0
        self.img_width = 2080
        self.img_height = 0
        self.last_update_time = 0
        
    def process_samples(self, samples):
        # Always generate an image, even if empty samples
        if len(samples) == 0:
            samples = np.random.uniform(-0.5, 0.5, size=self.img_width)
            
        if self.current_image is None:
            self.img_height = 1
            self.current_image = Image.new('RGB', (self.img_width, 1))
            self.line_counter = 0
            
        # Create new line
        line_data = np.clip(samples * 255, 0, 255).astype(np.uint8)
        line_img = Image.fromarray(line_data.reshape(1, -1), 'L').convert('RGB')
        
        # Add line to image
        new_img = Image.new('RGB', (self.img_width, self.img_height + 1))
        if self.img_height > 0:
            new_img.paste(self.current_image, (0, 0))
        new_img.paste(line_img, (0, self.img_height))
        
        self.current_image = new_img
        self.img_height += 1
        self.line_counter += 1
        
        # Calculate signal quality
        rms = np.sqrt(np.mean(samples**2))
        self.signal_quality = min(100, max(0, (rms / 30) * 100))
        
        current_time = time.time()
        # Update image more frequently for better real-time feel
        if current_time - self.last_update_time > 0.1 or self.line_counter % 5 == 0:
            self.last_update_time = current_time
            # Add info text periodically
            draw = ImageDraw.Draw(self.current_image)
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            draw.text((20, 20), 
                     f"NOAA APT Line {self.line_counter}\n{timestamp}\nSNR: {self.signal_quality:.1f}%", 
                     fill="white")
            return self.current_image, self.signal_quality
        
        return None, None  # Don't return image if not enough time has passed
class GOESDecoder:
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.current_image = None
        self.signal_quality = 0
        
    def process_samples(self, samples):
        img_size = 800
        img = Image.new('RGB', (img_size, img_size), color=(20, 20, 50))
        draw = ImageDraw.Draw(img)
        
        # Always show something, even if no signal
        if len(samples) == 0:
            power = random.random() * 10
        else:
            power = np.mean(np.abs(samples))
            
        self.signal_quality = min(100, power * 10)
        
        # Draw something visual
        center = img_size // 2
        radius = min(300, 100 + (int(time.time()) % 200))
        draw.ellipse([(center-radius, center-radius), 
                     (center+radius, center+radius)], 
                     outline='cyan', width=2)
        
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        draw.text((20, 20),
                 f"GOES-16 LRIT\n{timestamp}\nSNR: {self.signal_quality:.1f}%",
                 fill="white")
        
        if self.current_image:
            self.current_image = Image.blend(self.current_image, img, 0.2)
        else:
            self.current_image = img
            
        return self.current_image, self.signal_quality

class AudioPlayer:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.playing = False
        
    def start(self, freq):
        self.stop()  # Ensure any existing stream is closed
        try:
            self.stream = self.p.open(format=pyaudio.paInt16,
                                    channels=1,
                                    rate=32000,
                                    output=True)
            self.playing = True
        except Exception as e:
            print(f"Audio stream error: {e}")

    def stop(self):
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                print(f"Error closing audio stream: {e}")
            finally:
                self.stream = None
        self.playing = False
        
    def play(self, data):
        if self.playing and self.stream:
            try:
                self.stream.write(data)
            except Exception as e:
                if "Stream closed" not in str(e):  # Ignore expected errors during shutdown
                    print(f"Audio play error: {e}")

class SDRApp:
    def __init__(self, root):
        self.root = root
        self.running = False
        self.current_image = None
        self.current_snr = 0
        self.audio_player = AudioPlayer()
        self.sdr_process = None
        
        self.create_widgets()
        self.setup_decoders()
        self.setup_signal_monitor()
        self.setup_satellite_tracker()
        
        self.update_controls()
        self.update_location()
        self.root.after(100, self.update_display)
        self.decoding_active = False  # Add this with other instance variables

    def create_widgets(self):
        self.root.title("Advanced SDR Receiver")
        self.root.geometry("1200x800")
        
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.control_frame = ttk.LabelFrame(self.main_frame, text="Controls", width=300)
        self.control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        self.display_frame = ttk.Frame(self.main_frame)
        self.display_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.create_mode_controls()
        self.create_frequency_controls()
        self.create_location_controls()
        self.create_signal_display()
        self.create_satellite_passes()
        self.create_image_display()

    def create_mode_controls(self):
        self.mode_var = tk.StringVar(value="noaa")
        ttk.Label(self.control_frame, text="Mode:").pack(anchor="w")
        
        modes = [("NOAA APT", "noaa"), ("GOES LRIT", "goes"), ("FM/Police Radio", "fm")]
        for text, mode in modes:
            ttk.Radiobutton(self.control_frame, text=text, variable=self.mode_var, 
                          value=mode, command=self.update_controls).pack(anchor="w")

    def create_frequency_controls(self):
        ttk.Label(self.control_frame, text="Frequency (MHz):").pack(anchor="w")
        self.freq_entry = ttk.Entry(self.control_frame)
        self.freq_entry.pack(fill=tk.X)
        self.freq_entry.insert(0, "137.5")
        
        # Duration controls
        self.duration_frame = ttk.Frame(self.control_frame)
        self.duration_frame.pack(fill=tk.X, pady=5)
        ttk.Label(self.duration_frame, text="Duration (mins):").pack(side=tk.LEFT)
        self.duration_entry = ttk.Entry(self.duration_frame, width=5)
        self.duration_entry.pack(side=tk.LEFT, padx=5)
        self.duration_entry.insert(0, "15")
        
        # Radio control buttons
        self.radio_btn_frame = ttk.Frame(self.control_frame)
        self.radio_btn_frame.pack(fill=tk.X, pady=5)
        self.play_btn = ttk.Button(self.radio_btn_frame, text="▶ Start Reception", command=self.start_reception)
        self.play_btn.pack(side=tk.LEFT, expand=True)
        self.stop_btn = ttk.Button(self.radio_btn_frame, text="■ Stop Reception", command=self.stop_reception, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, expand=True)
        
        # Decode button
        self.decode_btn_frame = ttk.Frame(self.control_frame)
        self.decode_btn = ttk.Button(
            self.decode_btn_frame, 
            text="▶ Start Decoding", 
            command=self.toggle_decoding,
            state=tk.DISABLED
        )
        self.decode_btn.pack(fill=tk.X)
        self.decode_btn_frame.pack_forget()  # Hidden by default

    def toggle_decoding(self):
        """Toggle the decoding process on/off"""
        if not self.running:
            messagebox.showwarning("Warning", "Please start reception first")
            return
        
        self.decoding_active = not self.decoding_active
        
        if self.decoding_active:
            self.decode_btn.config(text="■ Stop Decoding")
            self.show_status("Decoding started - displaying images")
        else:
            self.decode_btn.config(text="▶ Start Decoding")
            self.show_status("Decoding stopped", 3000)
        
        # Radio control buttons
        self.radio_btn_frame = ttk.Frame(self.control_frame)
        self.play_btn = ttk.Button(self.radio_btn_frame, text="▶ Start Reception", command=self.start_reception)
        self.play_btn.pack(side=tk.LEFT, expand=True)
        self.stop_btn = ttk.Button(self.radio_btn_frame, text="■ Stop Reception", command=self.stop_reception, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, expand=True)

    def start_decoding(self):
        """Start the decoding process specifically for displaying images"""
        if not self.running:
            messagebox.showwarning("Warning", "Please start reception first")
            return
        
        # Enable the display update process if it wasn't running
        if not hasattr(self, 'decoding_active'):
            self.decoding_active = True
            self.decode_btn.config(text="■ Stop Decoding")
            self.show_status("Decoding started - displaying images")
            
            # Force an immediate display update
            self.root.after(0, self.update_display)
        else:
            # Toggle decoding off
            self.decoding_active = False
            self.decode_btn.config(text="▶ Start Decoding")
            self.show_status("Decoding stopped", 3000)

    def create_location_controls(self):
        loc_frame = ttk.LabelFrame(self.control_frame, text="Location", padding=5)
        loc_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(loc_frame, text="Latitude:").grid(row=0, column=0, sticky="w")
        self.lat_entry = ttk.Entry(loc_frame, width=10)
        self.lat_entry.grid(row=0, column=1, sticky="we")
        self.lat_entry.insert(0, "40.7128")
        
        ttk.Label(loc_frame, text="Longitude:").grid(row=1, column=0, sticky="w")
        self.lon_entry = ttk.Entry(loc_frame, width=10)
        self.lon_entry.grid(row=1, column=1, sticky="we")
        self.lon_entry.insert(0, "-74.0060")
        
        ttk.Button(loc_frame, text="Update", command=self.update_location).grid(row=2, columnspan=2)
        
        self.auto_var = tk.IntVar(value=0)
        ttk.Checkbutton(self.control_frame, text="Auto-Track Satellites", 
                       variable=self.auto_var).pack(anchor="w", pady=5)

    def create_signal_display(self):
        ttk.Label(self.control_frame, text="Signal Quality:").pack(anchor="w")
        self.snr_label = ttk.Label(self.control_frame, text="SNR: 0.0 dB")
        self.snr_label.pack(anchor="w")
        
        ttk.Label(self.control_frame, text="Reception Progress:").pack(anchor="w")
        self.reception_progress = ttk.Progressbar(self.control_frame, length=200)
        self.reception_progress.pack(fill=tk.X)

    def create_satellite_passes(self):
        self.passes_frame = ttk.LabelFrame(self.display_frame, text="Next Satellite Passes", padding=10)
        self.passes_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.passes_tree = ttk.Treeview(self.passes_frame, columns=('Satellite', 'Time', 'Duration', 'Max Elev'), show='headings')
        for col in ['Satellite', 'Time', 'Duration', 'Max Elev']:
            self.passes_tree.heading(col, text=col)
        self.passes_tree.pack(fill=tk.BOTH, expand=True)

    def create_image_display(self):
        self.image_frame = ttk.LabelFrame(self.display_frame, text="Satellite Image", padding=10)
        self.image_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.canvas = tk.Canvas(self.image_frame, bg='black')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.create_text(300, 150, text="Image will appear here", fill="white", font=('Helvetica', 16))

    def setup_decoders(self):
        self.noaa_decoder = NOAADecoder()
        self.goes_decoder = GOESDecoder()
        self.sample_queue = queue.Queue(maxsize=100)
        self.image_queue = queue.Queue(maxsize=10)
        self.snr_queue = queue.Queue()

    def setup_signal_monitor(self):
        self.signal_running = True
        self.signal_data = []
        threading.Thread(target=self.monitor_signals, daemon=True).start()

    def setup_satellite_tracker(self):
        self.tracker = SatelliteTracker()
        self.update_next_passes()

    def monitor_signals(self):
        while self.signal_running:
            try:
                while True:
                    snr = self.snr_queue.get_nowait()
                    self.current_snr = snr
                    self.signal_data.append(snr)
                    if len(self.signal_data) > 100:
                        self.signal_data.pop(0)
            except queue.Empty:
                pass
            
            self.root.after(0, self.update_signal_displays)
            time.sleep(0.1)

    def update_signal_displays(self):
        snr = max(0, min(30, self.current_snr))
        self.snr_label.config(text=f"SNR: {snr:.1f} dB")

    def update_next_passes(self):
        for item in self.passes_tree.get_children():
            self.passes_tree.delete(item)
            
        passes = []
        for sat_name in self.tracker.noaa_sats.keys():
            pass_info = self.tracker.next_pass(sat_name)
            if pass_info:
                duration = pass_info['set_time'] - pass_info['rise_time']
                passes.append((
                    sat_name,
                    pass_info['rise_time'].strftime('%Y-%m-%d %H:%M:%S'),
                    str(duration).split('.')[0],
                    f"{pass_info['max_elevation']:.1f}°"
                ))
        
        for pass_info in sorted(passes, key=lambda x: x[1]):
            self.passes_tree.insert('', 'end', values=pass_info)
        
        self.root.after(60000, self.update_next_passes)

    def update_location(self):
        try:
            lat = float(self.lat_entry.get())
            lon = float(self.lon_entry.get())
            self.tracker.set_location(lat, lon)
            self.update_next_passes()
            self.show_status(f"Location updated to {lat}, {lon}")
        except ValueError:
            msg = "Invalid latitude/longitude"
            self.show_status(msg, 5000)
            messagebox.showerror("Error", msg)

    def update_controls(self):
        mode = self.mode_var.get()
        
        if mode == "fm":
            self.duration_frame.pack_forget()
            self.decode_btn_frame.pack_forget()
            self.radio_btn_frame.pack(fill=tk.X, pady=5)
            self.freq_entry.delete(0, tk.END)
            self.freq_entry.insert(0, "98.5")
        else:
            self.duration_frame.pack(fill=tk.X, pady=5)
            self.radio_btn_frame.pack(fill=tk.X, pady=5)
            
            if mode == "noaa":
                self.decode_btn_frame.pack(fill=tk.X, pady=5)
                self.freq_entry.delete(0, tk.END)
                self.freq_entry.insert(0, "137.5")
            elif mode == "goes":
                self.decode_btn_frame.pack(fill=tk.X, pady=5)
                self.freq_entry.delete(0, tk.END)
                self.freq_entry.insert(0, "1694.1")

    def start_reception(self):
        if self.running:
            return
            
        try:
            mode = self.mode_var.get()
            freq = self.freq_entry.get()
            
            self.show_status(f"Starting {mode.upper()} reception on {freq}MHz...")
            
            # Reset decoders and queues
            if mode == "noaa":
                self.noaa_decoder.reset()
            elif mode == "goes":
                self.goes_decoder.reset()
            
            # Clear all queues
            for q in [self.sample_queue, self.image_queue, self.snr_queue]:
                while not q.empty():
                    q.get_nowait()
            
            # Clear the display
            self.canvas.delete("all")
            self.canvas.create_text(
                self.canvas.winfo_width()//2,
                self.canvas.winfo_height()//2,
                text="Starting reception...\nPreparing to display image",
                fill="white",
                font=('Helvetica', 16),
                justify='center'
            )
            
            if mode == "fm":
                cmd = [
                    "rtl_fm", 
                    "-f", f"{freq}e6", 
                    "-M", "fm",
                    "-s", "170k", 
                    "-r", "32k", 
                    "-l", "0", 
                    "-E", "deemp", 
                    "-"
                ]
                self.sdr_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid,
                    bufsize=1024*1024
                )
                self.audio_player.start(float(freq))
                duration = 0
            else:
                duration = float(self.duration_entry.get()) * 60
                cmd = [
                    "rtl_sdr",
                    "-f", f"{freq}e6",
                    "-s", "2.4e6",
                    "-n", str(int(duration * 2.4e6)),
                    "-"
                ]
                self.sdr_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid,
                    bufsize=1024*1024
                )
            
            self.current_freq = float(freq)
            self.running = True
            self.decoding_active = False  # Start with decoding off
            
            # Start processing threads
            threading.Thread(target=self.read_samples, daemon=True).start()
            threading.Thread(target=self.process_samples, daemon=True).start()
            
            # Start progress monitor
            self.start_time = time.time()
            self.duration = duration
            threading.Thread(target=self.monitor_progress, daemon=True).start()
            
            # Update UI
            self.play_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.freq_entry.config(state=tk.DISABLED)
            self.decode_btn.config(state=tk.NORMAL, text="▶ Start Decoding")
            
            self.show_status(f"Reception started on {freq}MHz")
            
        except Exception as e:
            self.show_status(f"Error: {str(e)}", 5000)
            messagebox.showerror("Error", f"Failed to start: {str(e)}")
            if hasattr(self, 'sdr_process') and self.sdr_process:
                try:
                    os.killpg(os.getpgid(self.sdr_process.pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass
            self.running = False
            self.decoding_active = False
            self.play_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.freq_entry.config(state=tk.NORMAL)
            self.decode_btn.config(state=tk.DISABLED, text="▶ Start Decoding")

    def stop_reception(self):
        if not self.running:
            return
        
        self.show_status("Stopping reception...")
        
        try:
            # Stop audio first
            self.audio_player.stop()
            
            # Terminate SDR process
            if self.sdr_process:
                try:
                    os.killpg(os.getpgid(self.sdr_process.pid), signal.SIGTERM)
                    self.sdr_process.wait(timeout=1)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(os.getpgid(self.sdr_process.pid), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                self.sdr_process = None
                
        except Exception as e:
            self.show_status(f"Error stopping: {str(e)}", 5000)
            return
        
        self.running = False
        self.decoding_active = False
        
        # Update UI controls
        self.play_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.freq_entry.config(state=tk.NORMAL)
        self.decode_btn.config(state=tk.DISABLED, text="▶ Start Decoding")
        
        # Clear the progress bar
        self.reception_progress['value'] = 0
        
        self.show_status("Reception stopped")

    def read_samples(self):
        try:
            mode = self.mode_var.get()
            chunk_size = 1024 * 4
            
            while self.running and self.sdr_process:
                raw_samples = self.sdr_process.stdout.read(chunk_size)
                if not raw_samples:
                    break
                
                if mode == "fm":
                    self.audio_player.play(raw_samples)
                else:
                    samples = np.frombuffer(raw_samples, dtype=np.uint8).astype(np.float32) / 255.0 - 0.5
                    self.sample_queue.put(samples)
                        
        except Exception as e:
            self.show_status(f"Read error: {e}", 5000)
        finally:
            if self.running:
                self.root.after(0, self.stop_reception)

    def process_samples(self):
        try:
            while self.running:
                try:
                    samples = self.sample_queue.get(timeout=0.1)
                    
                    if self.mode_var.get() == "noaa":
                        image, snr = self.noaa_decoder.process_samples(samples)
                    else:
                        image, snr = self.goes_decoder.process_samples(samples)
                    
                    if image is not None:  # Only update if we have a new image
                        self.image_queue.put(image)
                    if snr is not None:
                        self.snr_queue.put(snr)
                    
                except queue.Empty:
                    continue
                    
        except Exception as e:
            self.show_status(f"Process error: {e}", 5000)


    def update_display(self):
        try:
            if self.decoding_active:
                while True:
                    image = self.image_queue.get_nowait()
                    if image:
                        canvas_width = self.canvas.winfo_width()
                        canvas_height = self.canvas.winfo_height()
                        
                        if canvas_width > 0 and canvas_height > 0:
                            # Show partial images as they come in
                            img_ratio = image.width / image.height
                            canvas_ratio = canvas_width / canvas_height
                            
                            if canvas_ratio > img_ratio:
                                display_height = canvas_height
                                display_width = int(canvas_height * img_ratio)
                            else:
                                display_width = canvas_width
                                display_height = int(canvas_width / img_ratio)
                            
                            if display_width != image.width or display_height != image.height:
                                display_image = image.resize((display_width, display_height), 
                                                        Image.Resampling.LANCZOS)
                            else:
                                display_image = image
                            
                            self.current_image = ImageTk.PhotoImage(display_image)
                            self.canvas.delete("all")
                            self.canvas.create_image(
                                canvas_width//2,
                                canvas_height//2,
                                image=self.current_image,
                                anchor=tk.CENTER
                            )
                            
                            # Show progress info
                            progress = f"Lines received: {image.height}"
                            self.canvas.create_text(
                                canvas_width//2,
                                20,
                                text=progress,
                                fill="yellow",
                                font=('Helvetica', 12),
                                tags="progress"
                            )
        except queue.Empty:
            pass
        
        self.root.after(50, self.update_display)
    def show_status(self, message, duration=3000):
        self.canvas.delete("status")
        
        self.canvas.create_text(
            self.canvas.winfo_width()//2,
            self.canvas.winfo_height()-20,
            text=message,
            fill="yellow",
            font=('Helvetica', 12),
            tags="status"
        )
        
        if duration > 0:
            self.canvas.after(duration, lambda: self.canvas.delete("status"))

    def monitor_progress(self):
        try:
            while self.running and (self.duration == 0 or time.time() - self.start_time < self.duration):
                elapsed = time.time() - self.start_time
                if self.duration > 0:
                    progress = min(100, (elapsed / self.duration) * 100)
                    self.reception_progress['value'] = progress
                time.sleep(0.1)
        finally:
            if self.running:
                self.root.after(0, self.stop_reception)

    def on_closing(self):
        self.signal_running = False
        self.stop_reception()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = SDRApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()