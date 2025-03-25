#--------{IMPORTS}--------
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import os
import signal
from PIL import Image, ImageTk, ImageDraw
import numpy as np
import queue
import threading
import time
from datetime import datetime
import io

#--------{GOES DECODER CLASS}--------
class GOESDecoder:
    def __init__(self):
        self.current_image = None
        self.last_update = time.time()
        self.image_sequence = 0
        
    def process_samples(self, samples):
        """
        Process GOES LRIT samples and generate images
        Replace this with actual LRIT decoding in production
        """
        # Create blank image
        img_size = 800
        img = Image.new('RGB', (img_size, img_size), color=(20, 20, 50))
        draw = ImageDraw.Draw(img)
        
        # Add simulated satellite data
        center = img_size // 2
        radius = min(300, 100 + (self.image_sequence % 200))
        draw.ellipse([(center-radius, center-radius), 
                    (center+radius, center+radius)], 
                    outline='cyan', width=2)
        
        # Add info text
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        draw.text((20, 20), 
                 f"GOES-16 LRIT Simulator\n{timestamp}\n"
                 f"Sequence: {self.image_sequence}\n"
                 "Replace with actual LRIT decoder",
                 fill="white")
        
        # Simulate scan lines
        for i in range(0, img_size, 15):
            brightness = int(50 + 100 * abs(np.sin(i/50 + self.image_sequence/10)))
            draw.line([(0,i), (img_size,i)], fill=(0, brightness, brightness), width=1)
        
        self.image_sequence += 1
        return img

#--------{MAIN APPLICATION CLASS}--------
class SDRApp:
    def __init__(self, root):
        self.root = root
        self.process = None
        self.running = False
        self.image_path = None
        self.progress_queue = queue.Queue()
        self.sample_queue = queue.Queue()
        self.goes_decoder = GOESDecoder()
        
        #--------{GUI INITIALIZATION}--------
        self.root.title("Satellite SDR Receiver")
        self.root.geometry("1000x800")
        self.setup_gui()
        
        #--------{BACKGROUND THREADS}--------
        self.start_threads()
        
        #--------{DEFAULT SETTINGS}--------
        self.update_frequency()

    #--------{GUI SETUP}--------
    def setup_gui(self):
        """Initialize all GUI components"""
        self.create_control_panel()
        self.create_image_display()
        self.create_progress_bars()
        self.create_menu()

    def create_control_panel(self):
        """Create the top control panel"""
        control_frame = ttk.LabelFrame(self.root, text="Receiver Controls", padding=10)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Mode selection
        ttk.Label(control_frame, text="Mode:").grid(row=0, column=0, sticky="w")
        self.mode_var = tk.StringVar(value="noaa")
        
        modes = [
            ("NOAA APT", "noaa"),
            ("GOES LRIT", "goes"),
            ("FM Radio", "fm")
        ]
        
        for i, (text, mode) in enumerate(modes):
            ttk.Radiobutton(control_frame, text=text, variable=self.mode_var, 
                          value=mode, command=self.update_frequency).grid(row=0, column=i+1, sticky="w")
        
        # Frequency control
        ttk.Label(control_frame, text="Frequency (MHz):").grid(row=1, column=0, sticky="w")
        self.freq_entry = ttk.Entry(control_frame, width=10)
        self.freq_entry.grid(row=1, column=1, sticky="w")
        
        # Duration control
        ttk.Label(control_frame, text="Duration (mins):").grid(row=1, column=2, sticky="w")
        self.duration_entry = ttk.Entry(control_frame, width=5)
        self.duration_entry.insert(0, "10")
        self.duration_entry.grid(row=1, column=3, sticky="w")
        
        # Control buttons
        self.start_btn = ttk.Button(control_frame, text="Start", command=self.start_reception)
        self.start_btn.grid(row=2, column=1, pady=5)
        
        self.stop_btn = ttk.Button(control_frame, text="Stop", command=self.stop_reception, state=tk.DISABLED)
        self.stop_btn.grid(row=2, column=2, pady=5)
        
        # Status display
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(control_frame, textvariable=self.status_var).grid(row=3, columnspan=4)

    def create_image_display(self):
        """Create the image display area"""
        self.image_frame = ttk.LabelFrame(self.root, text="Satellite Images", padding=10)
        self.image_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Canvas for images
        self.canvas = tk.Canvas(self.image_frame, bg='black')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Image controls
        btn_frame = ttk.Frame(self.image_frame)
        btn_frame.pack(pady=5)
        
        ttk.Button(btn_frame, text="Decode NOAA", command=self.decode_noaa).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Save Image", command=self.save_image).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Clear", command=self.clear_display).pack(side=tk.LEFT, padx=5)

    def create_progress_bars(self):
        """Create progress bars"""
        self.progress_frame = ttk.LabelFrame(self.root, text="Progress", padding=10)
        self.progress_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Reception progress
        ttk.Label(self.progress_frame, text="Reception:").grid(row=0, column=0, sticky="w")
        self.reception_progress = ttk.Progressbar(self.progress_frame, length=300)
        self.reception_progress.grid(row=0, column=1, sticky="ew")
        
        # Decoding progress
        ttk.Label(self.progress_frame, text="Decoding:").grid(row=1, column=0, sticky="w")
        self.decode_progress = ttk.Progressbar(self.progress_frame, length=300)
        self.decode_progress.grid(row=1, column=1, sticky="ew")

    def create_menu(self):
        """Create menu bar"""
        menubar = tk.Menu(self.root)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Image", command=self.load_image)
        file_menu.add_command(label="Exit", command=self.on_closing)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        self.root.config(menu=menubar)

    #--------{THREAD MANAGEMENT}--------
    def start_threads(self):
        """Start background threads"""
        self.goes_running = True
        self.decoder_thread = threading.Thread(target=self.run_goes_decoder, daemon=True)
        self.decoder_thread.start()
        
        self.progress_thread = threading.Thread(target=self.monitor_progress, daemon=True)
        self.progress_thread.start()
        
        self.root.after(100, self.check_threads)

    def check_threads(self):
        """Periodically check thread status"""
        if not self.decoder_thread.is_alive() and self.goes_running:
            self.decoder_thread = threading.Thread(target=self.run_goes_decoder, daemon=True)
            self.decoder_thread.start()
        
        self.root.after(1000, self.check_threads)

    #--------{RECEPTION CONTROL}--------
    def update_frequency(self):
        """Update frequency based on selected mode"""
        mode = self.mode_var.get()
        self.freq_entry.delete(0, tk.END)
        
        if mode == "noaa":
            self.freq_entry.insert(0, "137.5")
        elif mode == "goes":
            self.freq_entry.insert(0, "1694.1")  # GOES West
        else:  # FM
            self.freq_entry.insert(0, "98.5")

    def start_reception(self):
        """Start SDR reception based on selected mode"""
        if self.running:
            return
            
        try:
            freq = float(self.freq_entry.get())
            mode = self.mode_var.get()
            duration = int(self.duration_entry.get()) if mode in ["noaa", "goes"] else 0
            
            self.start_time = time.time()
            self.duration = duration
            
            if mode == "noaa":
                self.start_noaa(freq, duration)
            elif mode == "goes":
                self.start_goes(freq, duration)
            else:  # FM
                self.start_fm(freq)
                
            self.running = True
            self.update_ui_state(running=True)
            self.status_var.set(f"Receiving {mode.upper()} at {freq} MHz")
            
        except ValueError:
            messagebox.showerror("Error", "Invalid frequency or duration")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start: {str(e)}")

    def start_noaa(self, freq, duration):
        """Start NOAA APT reception"""
        cmd = [
            "rtl_fm",
            "-f", f"{freq}e6",
            "-M", "wbfm",
            "-s", "60k",
            "-r", "48k",
            "-T", str(duration * 60),  # Convert to seconds
            "-E", "wav",
            "-F", "9",
            "-"
        ]
        
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        
        # Start thread to monitor recording
        threading.Thread(target=self.monitor_recording, daemon=True).start()

    def start_goes(self, freq, duration):
        """Start GOES LRIT reception with real-time processing"""
        cmd = [
            "rtl_fm",
            "-f", f"{freq}e6",
            "-M", "wbfm",
            "-s", "240k",  # Higher sample rate for GOES
            "-r", "48k",
            "-T", str(duration * 60),
            "-E", "wav",
            "-F", "9",
            "-"
        ]
        
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid,
            bufsize=1024*8
        )
        
        # Start sample reading thread
        threading.Thread(target=self.read_goes_samples, daemon=True).start()

    def start_fm(self, freq):
        """Start FM radio reception"""
        cmd = [
            "rtl_fm",
            "-f", f"{freq}e6",
            "-M", "fm",
            "-s", "200k",
            "-r", "44.1k",
            "-"
        ]
        
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        
        # Pipe to audio player
        play_cmd = [
            "play",
            "-r", "44.1k",
            "-t", "raw",
            "-e", "s",
            "-b", "16",
            "-c", "1",
            "-V1",
            "-"
        ]
        
        self.audio_process = subprocess.Popen(
            play_cmd,
            stdin=self.process.stdout,
            stderr=subprocess.PIPE
        )

    def stop_reception(self):
        """Stop all reception and processing"""
        self.goes_running = False
        self.running = False
        
        if hasattr(self, 'process') and self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
            self.process = None
            
        if hasattr(self, 'audio_process') and self.audio_process:
            self.audio_process.terminate()
            
        self.update_ui_state(running=False)
        self.status_var.set("Ready")

    #--------{BACKGROUND PROCESSING}--------
    def read_goes_samples(self):
        """Read GOES samples from rtl_fm output"""
        try:
            while self.running and self.process.poll() is None:
                # Read raw samples in chunks
                raw_samples = self.process.stdout.read(1024*4)
                if raw_samples:
                    # Convert to numpy array (real implementation would demodulate)
                    samples = np.frombuffer(raw_samples, dtype=np.uint8)
                    self.sample_queue.put(samples)
                    
                    # Update progress
                    elapsed = time.time() - self.start_time
                    progress = min(100, (elapsed / (self.duration * 60)) * 100)
                    self.progress_queue.put(("reception", progress))
        except Exception as e:
            self.progress_queue.put(("status", f"Error: {str(e)}"))
        finally:
            if hasattr(self, 'process') and self.process:
                self.process.stdout.close()

    def run_goes_decoder(self):
        """Continuous GOES LRIT decoding thread"""
        while self.goes_running:
            try:
                samples = self.sample_queue.get(timeout=0.1)
                if samples is not None and self.mode_var.get() == "goes":
                    # Process samples into image
                    image = self.goes_decoder.process_samples(samples)
                    
                    # Update display
                    self.display_goes_image(image)
                    
                    # Update progress
                    self.progress_queue.put(("decoding", 
                                           min(100, self.goes_decoder.image_sequence % 100)))
                    
            except queue.Empty:
                continue
            except Exception as e:
                self.progress_queue.put(("status", f"Decoder error: {str(e)}"))

    def monitor_recording(self):
        """Monitor recording progress for NOAA"""
        try:
            while self.running and self.process.poll() is None:
                elapsed = time.time() - self.start_time
                progress = min(100, (elapsed / (self.duration * 60)) * 100)
                self.progress_queue.put(("reception", progress))
                time.sleep(1)
                
            self.progress_queue.put(("reception", 100))
        except Exception as e:
            self.progress_queue.put(("status", f"Monitor error: {str(e)}"))

    def monitor_progress(self):
        """Update progress bars from queue"""
        try:
            while True:
                item = self.progress_queue.get_nowait()
                if item[0] == "reception":
                    self.reception_progress['value'] = item[1]
                elif item[0] == "decoding":
                    self.decode_progress['value'] = item[1]
                elif item[0] == "status":
                    self.status_var.set(item[1])
        except queue.Empty:
            pass
        
        self.root.after(100, self.monitor_progress)

    #--------{IMAGE HANDLING}--------
    def display_goes_image(self, image):
        """Display GOES image with thread-safe update"""
        try:
            # Resize for display while maintaining aspect ratio
            img_width, img_height = image.size
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            scale = min(canvas_width/img_width, canvas_height/img_height)
            new_size = (int(img_width*scale), int(img_height*scale))
            
            if scale < 1:  # Only resize if needed
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage
            self.tk_img = ImageTk.PhotoImage(image)
            
            # Thread-safe GUI update
            self.root.after(0, lambda: self.update_canvas(image))
            
            # Save to file
            self.image_path = f"goes_image_{int(time.time())}.png"
            image.save(self.image_path)
            
        except Exception as e:
            self.progress_queue.put(("status", f"Display error: {str(e)}"))

    def update_canvas(self, image):
        """Update canvas with new image"""
        self.canvas.delete("all")
        self.canvas.create_image(
            self.canvas.winfo_width()//2,
            self.canvas.winfo_height()//2,
            anchor="center",
            image=self.tk_img
        )

    def decode_noaa(self):
        """Decode NOAA APT recording"""
        if not os.path.exists("noaa_raw.wav"):
            messagebox.showwarning("Warning", "No NOAA recording found")
            return
            
        try:
            # Start decoding in thread
            threading.Thread(target=self.run_noaa_decoding, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", f"Decoding failed: {str(e)}")

    def run_noaa_decoding(self):
        """NOAA APT decoding process"""
        try:
            self.progress_queue.put(("decoding", 10))
            
            # Convert to WXtoImg compatible format
            subprocess.run([
                "sox", 
                "noaa_raw.wav", 
                "-r", "11025", 
                "noaa_input.wav"
            ], check=True)
            self.progress_queue.put(("decoding", 30))
            
            # Try using WXtoImg if installed
            if os.path.exists("/Applications/WXtoImg.app"):
                subprocess.run([
                    "/Applications/WXtoImg.app/Contents/MacOS/WXtoImg",
                    "-o", "noaa_input.wav"
                ], check=True)
                self.progress_queue.put(("decoding", 90))
                
                # Display the result
                if os.path.exists("noaa_output.png"):
                    self.display_noaa_image("noaa_output.png")
            else:
                # Fallback: generate placeholder
                self.generate_noaa_placeholder()
            
            self.progress_queue.put(("decoding", 100))
            
        except Exception as e:
            self.progress_queue.put(("decoding", 0))
            self.progress_queue.put(("status", f"Decoding error: {str(e)}"))

    def display_noaa_image(self, path):
        """Display NOAA APT image"""
        try:
            image = Image.open(path)
            self.image_path = path
            self.tk_img = ImageTk.PhotoImage(image)
            self.update_canvas(image)
        except Exception as e:
            messagebox.showerror("Error", f"Cannot display image: {str(e)}")

    def generate_noaa_placeholder(self):
        """Generate NOAA placeholder when WXtoImg not available"""
        img = Image.new('RGB', (800, 500), color=(0, 20, 40))
        draw = ImageDraw.Draw(img)
        
        # Draw simulated NOAA scan lines
        for i in range(0, 500, 2):
            brightness = int(50 + 100 * abs(np.sin(i/50)))
            draw.line([(0,i), (800,i)], fill=(0, brightness, brightness), width=1)
        
        # Add info text
        draw.text((20, 20), 
                 "NOAA APT Placeholder\nInstall WXtoImg for real decoding\n"
                 f"File: noaa_input.wav",
                 fill="white")
        
        self.tk_img = ImageTk.PhotoImage(img)
        self.update_canvas(img)
        self.image_path = "noaa_placeholder.png"
        img.save(self.image_path)

    #--------{FILE OPERATIONS}--------
    def load_image(self):
        """Load image from file"""
        path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png *.jpg *.jpeg")]
        )
        if path:
            try:
                image = Image.open(path)
                self.image_path = path
                self.tk_img = ImageTk.PhotoImage(image)
                self.update_canvas(image)
            except Exception as e:
                messagebox.showerror("Error", f"Cannot load image: {str(e)}")

    def save_image(self):
        """Save current image"""
        if not hasattr(self, 'image_path') or not self.image_path:
            messagebox.showwarning("Warning", "No image to save")
            return
            
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg")]
        )
        
        if path:
            try:
                img = Image.open(self.image_path)
                img.save(path)
                messagebox.showinfo("Success", f"Image saved to {path}")
            except Exception as e:
                messagebox.showerror("Error", f"Save failed: {str(e)}")

    def clear_display(self):
        """Clear the image display"""
        self.canvas.delete("all")
        self.canvas.create_text(
            self.canvas.winfo_width()//2,
            self.canvas.winfo_height()//2,
            text="Image display will appear here",
            fill="white"
        )
        self.image_path = None

    #--------{UI HELPERS}--------
    def update_ui_state(self, running):
        """Update UI elements based on running state"""
        self.start_btn.config(state=tk.DISABLED if running else tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL if running else tk.DISABLED)
        
        # Disable mode selection while running
        for child in self.root.winfo_children():
            if isinstance(child, ttk.Radiobutton):
                child.config(state=tk.DISABLED if running else tk.NORMAL)

    def show_about(self):
        """Show about dialog"""
        messagebox.showinfo(
            "About",
            "Satellite SDR Receiver\n\n"
            "Supports:\n"
            "- NOAA APT (137 MHz)\n"
            "- GOES LRIT (1694 MHz)\n"
            "- FM Radio (88-108 MHz)\n\n"
            "Note: GOES decoding is simulated\n"
            "Real decoding requires goesrecv"
        )

    def on_closing(self):
        """Handle window close"""
        self.stop_reception()
        self.root.destroy()

#--------{MAIN ENTRY POINT}--------
if __name__ == "__main__":
    root = tk.Tk()
    app = SDRApp(root)
    
    # Handle window close
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Start main loop
    root.mainloop()