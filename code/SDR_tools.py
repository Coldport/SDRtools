import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import os
import signal
from PIL import Image, ImageTk
import threading
import queue
import time

class SDRApp:
    def __init__(self, root):
        self.root = root
        self.process = None
        self.running = False
        self.image_path = None
        self.progress_queue = queue.Queue()
        
        # Configure main window
        self.root.title("SDR Controller")
        self.root.geometry("1000x800")
        
        # Create GUI components
        self.create_controls()
        self.create_image_display()
        self.create_progress_bars()
        
        # Set default frequency
        self.update_frequency()
        
        # Start progress monitor
        self.monitor_progress()

    def create_controls(self):
        """Create control panel with GOES options"""
        control_frame = ttk.LabelFrame(self.root, text="Satellite Controls", padding=10)
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
        
        # Frequency settings
        ttk.Label(control_frame, text="Frequency (MHz):").grid(row=1, column=0, sticky="w")
        self.freq_entry = ttk.Entry(control_frame, width=10)
        self.freq_entry.grid(row=1, column=1, sticky="w")
        
        # Record duration (for satellites)
        ttk.Label(control_frame, text="Record (mins):").grid(row=1, column=2, sticky="w")
        self.duration_entry = ttk.Entry(control_frame, width=5)
        self.duration_entry.insert(0, "10")
        self.duration_entry.grid(row=1, column=3, sticky="w")
        
        # Control buttons
        self.start_btn = ttk.Button(control_frame, text="Start", command=self.start_reception)
        self.start_btn.grid(row=2, column=1, pady=10)
        
        self.stop_btn = ttk.Button(control_frame, text="Stop", command=self.stop_reception, state=tk.DISABLED)
        self.stop_btn.grid(row=2, column=2, pady=10)
        
        # Status
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(control_frame, textvariable=self.status_var).grid(row=3, columnspan=4)

    def create_image_display(self):
        """Create image display area"""
        self.image_frame = ttk.LabelFrame(self.root, text="Satellite Images", padding=10)
        self.image_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.canvas = tk.Canvas(self.image_frame, bg='white')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Image controls
        btn_frame = ttk.Frame(self.image_frame)
        btn_frame.pack(pady=5)
        
        ttk.Button(btn_frame, text="Decode NOAA", command=self.decode_noaa).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Process GOES", command=self.process_goes).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Save Image", command=self.save_image).pack(side=tk.LEFT, padx=5)

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

    def update_frequency(self):
        """Update frequency based on mode"""
        mode = self.mode_var.get()
        self.freq_entry.delete(0, tk.END)
        
        if mode == "noaa":
            self.freq_entry.insert(0, "137.5")
        elif mode == "goes":
            self.freq_entry.insert(0, "1694.1")  # GOES West
        else:  # FM
            self.freq_entry.insert(0, "98.5")

    def start_reception(self):
        """Start SDR reception"""
        if self.running:
            return
            
        freq = self.freq_entry.get()
        mode = self.mode_var.get()
        duration = int(self.duration_entry.get()) * 60 if mode in ["noaa", "goes"] else 0
        
        try:
            if mode == "noaa":
                self.start_noaa(freq, duration)
            elif mode == "goes":
                self.start_goes(freq, duration)
            else:  # FM
                self.start_fm(freq)
                
            self.running = True
            self.update_ui_state(running=True)
            self.status_var.set(f"Receiving {mode.upper()} at {freq} MHz")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start: {str(e)}")

    def start_noaa(self, freq, duration):
        """Start NOAA reception"""
        cmd = f"rtl_fm -f {freq}e6 -M wbfm -s 60k -r 48k -T {duration} -E wav -F 9 - | sox -t raw -r 48k -e s -b 16 -c 1 -V1 - noaa_raw.wav"
        self.process = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)
        
        # Start progress monitor
        self.progress_thread = threading.Thread(target=self.monitor_recording, args=(duration,))
        self.progress_thread.start()

    def start_goes(self, freq, duration):
        """Start GOES reception (simplified)"""
        cmd = f"rtl_fm -f {freq}e6 -M wbfm -s 60k -r 48k -T {duration} -E wav -F 9 - | tee goes_raw.wav"
        self.process = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)
        
        # Start progress monitor
        self.progress_thread = threading.Thread(target=self.monitor_recording, args=(duration,))
        self.progress_thread.start()

    def start_fm(self, freq):
        """Start FM radio"""
        cmd = f"rtl_fm -f {freq}e6 -M fm -s 200k -r 44.1k | play -r 44.1k -t raw -e s -b 16 -c 1 -V1 -"
        self.process = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)

    def stop_reception(self):
        """Stop reception"""
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
            self.process = None
            
        self.running = False
        self.update_ui_state(running=False)
        self.status_var.set("Ready")

    def monitor_recording(self, duration):
        """Update progress bar during recording"""
        start_time = time.time()
        while self.running and (time.time() - start_time) < duration:
            progress = ((time.time() - start_time) / duration) * 100
            self.progress_queue.put(("reception", progress))
            time.sleep(1)
        
        self.progress_queue.put(("reception", 100))

    def monitor_progress(self):
        """Update progress bars from queue"""
        try:
            while True:
                bar_type, value = self.progress_queue.get_nowait()
                if bar_type == "reception":
                    self.reception_progress['value'] = value
                elif bar_type == "decoding":
                    self.decode_progress['value'] = value
        except queue.Empty:
            pass
        
        self.root.after(100, self.monitor_progress)

    def decode_noaa(self):
        """Decode NOAA audio using WXtoImg"""
        if not os.path.exists("noaa_raw.wav"):
            messagebox.showwarning("Warning", "No NOAA recording found")
            return
            
        try:
            # Start decoding in thread
            decode_thread = threading.Thread(target=self.run_noaa_decoding)
            decode_thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Decoding failed: {str(e)}")

    def run_noaa_decoding(self):
        """Actual NOAA decoding process"""
        try:
            self.progress_queue.put(("decoding", 10))
            
            # Convert audio format
            subprocess.run(["sox", "noaa_raw.wav", "-r", "11025", "noaa_input.wav"], check=True)
            self.progress_queue.put(("decoding", 30))
            
            # Use WXtoImg if available
            if os.path.exists("/Applications/WXtoImg.app"):
                subprocess.run([
                    "/Applications/WXtoImg.app/Contents/MacOS/WXtoImg",
                    "-o", "noaa_input.wav"
                ], check=True)
                self.progress_queue.put(("decoding", 90))
                self.display_image("noaa_output.png")
            else:
                self.display_placeholder("NOAA (Install WXtoImg for decoding)")
            
            self.progress_queue.put(("decoding", 100))
            
        except Exception as e:
            self.progress_queue.put(("decoding", 0))
            messagebox.showerror("Error", f"Decoding failed: {str(e)}")

    def process_goes(self):
        """Process GOES data (simplified)"""
        if not os.path.exists("goes_raw.wav"):
            messagebox.showwarning("Warning", "No GOES recording found")
            return
            
        try:
            # Simulate GOES processing
            for i in range(1, 101):
                time.sleep(0.05)
                self.progress_queue.put(("decoding", i))
            
            # Placeholder for actual GOES processing
            self.display_placeholder("GOES Image (Processing not implemented)")
            
        except Exception as e:
            messagebox.showerror("Error", f"GOES processing failed: {str(e)}")

    def display_image(self, path):
        """Display image on canvas"""
        try:
            img = Image.open(path)
            img.thumbnail((800, 500))
            self.tk_img = ImageTk.PhotoImage(img)
            self.canvas.create_image(400, 250, image=self.tk_img)
            self.image_path = path
        except Exception as e:
            messagebox.showerror("Error", f"Cannot display image: {str(e)}")
            self.display_placeholder("Image Error")

    def display_placeholder(self, text="Image"):
        """Show placeholder image with text"""
        img = Image.new('RGB', (800, 500), color='gray')
        self.tk_img = ImageTk.PhotoImage(img)
        self.canvas.create_image(400, 250, image=self.tk_img)
        self.canvas.create_text(400, 250, text=text, font=("Arial", 24))

    def save_image(self):
        """Save current image"""
        if not self.image_path:
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

    def update_ui_state(self, running):
        """Update UI elements"""
        self.start_btn.config(state=tk.DISABLED if running else tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL if running else tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = SDRApp(root)
    
    def on_closing():
        app.stop_reception()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()