import folium
from folium.plugins import MarkerCluster
from selenium import webdriver
from io import BytesIO
from PIL import Image
import webbrowser
import tempfile
import aiohttp
import asyncio
import math
from pyproj import Proj, transform
from datetime import datetime, timedelta
from threading import Thread
import os
import json
import time
import numpy as np
from scipy.signal import find_peaks
import matplotlib
matplotlib.use('Agg')  # Set the backend to non-interactive
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
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
import json
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

class Aircraft:
    def __init__(self, icao_id, callsign=""):
        self.icao_id = icao_id
        self.callsign = callsign
        self.positions = []  # List of (lat, lon, alt, timestamp) tuples
        self.altitude = 0
        self.speed = 0
        self.heading = 0
        self.last_update = datetime.min
        self.signal_strength = 0
        self.color = 'blue'  # Default color for aircraft

    def update_position(self, lat, lon, alt, timestamp, signal_strength):
        self.positions.append((lat, lon, alt, timestamp))
        self.altitude = alt
        self.last_update = timestamp
        self.signal_strength = signal_strength
        # Calculate speed and heading if we have at least 2 positions
        if len(self.positions) > 1:
            prev_pos = self.positions[-2]
            time_diff = (timestamp - prev_pos[3]).total_seconds()
            if time_diff > 0:
                # Calculate distance using Haversine formula
                R = 6371000  # Earth's radius in meters
                lat1, lon1 = math.radians(prev_pos[0]), math.radians(prev_pos[1])
                lat2, lon2 = math.radians(lat), math.radians(lon)
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                distance = R * c  # Distance in meters
                self.speed = distance / time_diff  # Speed in m/s
                # Calculate heading
                y = math.sin(lon2 - lon1) * math.cos(lat2)
                x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math  .cos(lat2) * math.cos(lon2 - lon1)
                self.heading = (math.  degrees(math.atan2(y, x)) + 360) % 360

class Tower:
    def __init__(self, name, lat, lon, freq, range_km=50):
        self.name = name
        self.lat = lat
        self.lon = lon
        self.frequency = freq
        self.range_km = range_km
        self.aircraft = {}  # icao_id: Aircraft objects
        self.last_scan = datetime.min

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
        
        # Always return image and SNR (no timing threshold)
        draw = ImageDraw.Draw(self.current_image)
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        draw.text((20, 20), 
                 f"NOAA APT Line {self.line_counter}\n{timestamp}\nSNR: {self.signal_quality:.1f}%", 
                 fill="white")
        return self.current_image, self.signal_quality
    

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

class PoliceAudioPlayer:
    """Specialized audio player for police/services frequencies with noise gate"""
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.playing = False
        self.noise_gate_level = 0.2  # Changed to float (0.0-1.0)
        self.enable_processing = True
        self.sample_rate = 32000  # Standard sample rate for voice
        self.audio_format = pyaudio.paInt16
        
    def start(self, freq):
        self.stop()  # Ensure any existing stream is closed
        try:
            self.stream = self.p.open(
                format=self.audio_format,
                channels=1,
                rate=self.sample_rate,
                output=True,
                frames_per_buffer=2048  # Added buffer size
            )
            self.playing = True
        except Exception as e:
            print(f"Police audio stream error: {e}")

    def stop(self):
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                print(f"Error closing police audio stream: {e}")
            finally:
                self.stream = None
        self.playing = False
        
    def set_noise_gate(self, level):
        """Set noise gate level (0-100) as percentage of max amplitude"""
        # Convert 0-100 scale to 0.0-1.0
        self.noise_gate_level = max(0.0, min(1.0, level / 100.0))
        
    def set_processing_enabled(self, enabled):
        """Enable/disable audio processing"""
        self.enable_processing = enabled
        
    def play(self, data):
        if not self.playing or not self.stream:
            return
            
        try:
            if not self.enable_processing:
                # Just play raw audio if processing is disabled
                self.stream.write(data)
                return
                
            # Convert bytes to numpy array of 16-bit integers
            samples = np.frombuffer(data, dtype=np.int16)
            
            if len(samples) == 0:
                return
                
            # Calculate threshold based on 16-bit range (-32768 to 32767)
            threshold = int(self.noise_gate_level * 32767)
            
            # Apply noise gate with smoother transition
            abs_samples = np.abs(samples)
            mask = abs_samples > threshold
            gated_samples = samples * mask
            
            # Optional: Add a small fade-in/out to avoid clicks
            # This creates a 5ms fade (at 32k sample rate)
            fade_samples = 160  # 5ms at 32k sample rate
            if fade_samples < len(gated_samples):
                # Fade in
                gated_samples[:fade_samples] = gated_samples[:fade_samples] * np.linspace(0, 1, fade_samples)
                # Fade out
                gated_samples[-fade_samples:] = gated_samples[-fade_samples:] * np.linspace(1, 0, fade_samples)
            
            # Convert back to bytes
            data = gated_samples.astype(np.int16).tobytes()
            
            # Play the processed audio
            self.stream.write(data)
        except Exception as e:
            if "Stream closed" not in str(e):  # Ignore expected errors during shutdown
                print(f"Police audio play error: {e}")

class SDRApp:
    def __init__(self, root):
        self.root = root
        self.running = False
        self.current_image = None
        self.current_snr = 0
        self.audio_player = AudioPlayer()
        self.police_audio_player = PoliceAudioPlayer()  # Add police audio player
        self.sdr_process = None
        self.police_frequencies = {}  # Store police frequencies data
        self.airport_frequencies = {}  # Store airport tower frequencies data
        
        self.load_police_frequencies()  # Load police frequencies from JSON
        self.load_airport_frequencies()  # Load airport tower frequencies from JSON
        self.create_widgets()
        self.setup_decoders()
        self.setup_signal_monitor()
        self.setup_satellite_tracker()
        
        self.update_controls()
        self.update_location()
        self.root.after(100, self.update_display)
        self.decoding_active = False
        # Scan mode variables
        self.scanning = False
        self.scan_thread_running = False
        self.scan_frequencies = []
        self.current_scan_index = 0
        self.scan_active_channels = []
        self.scan_signal_levels = {}
        self.map_thread_running = True

    def load_police_frequencies(self):
        """Load police frequencies from JSON file"""
        try:
            with open("police_frequencies.json", "r") as f:
                self.police_frequencies = json.load(f)
                print(f"Loaded police frequencies: {len(self.police_frequencies)} countries")
        except Exception as e:
            print(f"Error loading police frequencies: {e}")
            # Create a minimal default structure with the correct hierarchy: Country > State > City > Service
            self.police_frequencies = {
                "United States": {
                    "Example State": {
                        "Example City": {
                            "Police": [
                                "460.500 MHz - Example Police Dispatch"
                            ]
                        }
                    }
                }
            }
            
    def load_airport_frequencies(self):
        """Load airport tower frequencies from JSON file"""
        try:
            with open("airport_towers.json", "r") as f:
                self.airport_frequencies = json.load(f)
                print(f"Loaded airport tower frequencies: {len(self.airport_frequencies)} countries")
        except Exception as e:
            print(f"Error loading airport tower frequencies: {e}")
            # Create a minimal default structure
            self.airport_frequencies = {
                "United States": {
                    "Example State": {
                        "Example Airport (XXX)": {
                            "Tower": [
                                "118.000 MHz - Example Tower"
                            ]
                        }
                    }
                }
            }

    def create_widgets(self):
        self.root.title("SDR Tools")
        self.root.geometry("1200x800")
        self.root.configure(bg="#333333")
        
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.control_frame = ttk.Frame(self.main_frame, width=300)
        self.control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        self.display_frame = ttk.Frame(self.main_frame)
        self.display_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.create_mode_controls()
        
        # Create containers for each mode's specific UI
        self.noaa_frame = ttk.Frame(self.display_frame)
        self.fm_frame = ttk.Frame(self.display_frame)
        self.police_frame = ttk.Frame(self.display_frame)
        self.airport_frame = ttk.Frame(self.display_frame)  # Add airport frame
        
        self.create_frequency_controls()
        self.create_location_controls()
        self.create_signal_display()
        
        # Create mode-specific content
        self.create_noaa_content()
        self.create_fm_content()
        self.create_police_content()
        self.create_airport_content()  # Add airport content
        
        # Initialize airport_avail_freq_frame
        self.airport_avail_freq_frame = ttk.Frame(self.control_frame)
        self.airport_avail_freq_label = ttk.Label(self.airport_avail_freq_frame, text="Available Frequencies:")
        self.airport_avail_freq_label.pack(anchor="w", padx=5, pady=5)
        
        self.airport_freq_listbox = tk.Listbox(self.airport_avail_freq_frame, height=8)
        self.airport_freq_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.airport_freq_listbox.bind("<Double-1>", self.select_airport_frequency_from_list)
        
        self.airport_status_label = ttk.Label(self.airport_avail_freq_frame, text="")
        self.airport_status_label.pack(anchor="w", padx=5, pady=5)
        
        # Duration controls
        self.duration_frame = ttk.Frame(self.control_frame)
        ttk.Label(self.duration_frame, text="Duration (minutes):").pack(side=tk.LEFT)
        self.duration_entry = ttk.Entry(self.duration_frame, width=5)
        self.duration_entry.pack(side=tk.LEFT, padx=5)
        self.duration_entry.insert(0, "5")
        
        # Control buttons (shared across modes but will be configured differently)
        self.btn_frame = ttk.Frame(self.control_frame)
        self.btn_frame.pack(fill=tk.X, pady=5)
        
        self.play_btn = ttk.Button(self.btn_frame, text="▶ Start Reception", command=self.start_reception)
        self.play_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        
        self.stop_btn = ttk.Button(self.btn_frame, text="■ Stop Reception", command=self.stop_reception, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        
        # Decode button (for satellite modes)
        self.decode_btn = ttk.Button(self.control_frame, text="▶ Start Decoding", command=self.toggle_decoding, state=tk.DISABLED)
        
        # Start/Stop Audio buttons (for police and airport modes)
        self.audio_btn_frame = ttk.Frame(self.control_frame)
        self.start_audio_btn = ttk.Button(self.audio_btn_frame, text="Start Audio", command=self.start_audio)
        self.start_audio_btn.pack(side=tk.LEFT, padx=5)
        self.stop_audio_btn = ttk.Button(self.audio_btn_frame, text="Stop Audio", command=self.stop_audio)
        self.stop_audio_btn.pack(side=tk.LEFT, padx=5)

    def create_mode_controls(self):
        self.mode_var = tk.StringVar(value="noaa")
        ttk.Label(self.control_frame, text="Mode:").pack(anchor="w", pady=(10,0))
        
        modes = [
            ("NOAA APT", "noaa"), 
            ("GOES LRIT", "goes"), 
            ("FM Radio", "fm"),
            ("Police/Services", "police"),
            ("Airport Towers", "airport")  # Add airport mode
        ]
        
        for text, mode in modes:
            ttk.Radiobutton(self.control_frame, text=text, variable=self.mode_var, 
                          value=mode, command=self.update_controls).pack(anchor="w")

    def create_frequency_controls(self):
        ttk.Label(self.control_frame, text="Frequency (MHz):").pack(anchor="w", pady=(10,0))
        self.freq_entry = ttk.Entry(self.control_frame)
        self.freq_entry.pack(fill=tk.X, padx=5)
        self.freq_entry.insert(0, "137.5")

    def create_location_controls(self):
        self.location_frame = ttk.Frame(self.control_frame)
        self.location_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(self.location_frame, text="Location").pack(anchor="w")
        
        lat_frame = ttk.Frame(self.location_frame)
        lat_frame.pack(fill=tk.X, pady=2)
        ttk.Label(lat_frame, text="Latitude:").pack(side=tk.LEFT)
        self.lat_entry = ttk.Entry(lat_frame)
        self.lat_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.lat_entry.insert(0, "40.7128")
        
        lon_frame = ttk.Frame(self.location_frame)
        lon_frame.pack(fill=tk.X, pady=2)
        ttk.Label(lon_frame, text="Longitude:").pack(side=tk.LEFT)
        self.lon_entry = ttk.Entry(lon_frame)
        self.lon_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.lon_entry.insert(0, "-74.0060")
        
        update_btn = ttk.Button(self.location_frame, text="Update", command=self.update_location)
        update_btn.pack(pady=5)
        
        self.auto_var = tk.IntVar(value=0)
        ttk.Checkbutton(self.control_frame, text="Auto-Track Satellites", 
                       variable=self.auto_var).pack(anchor="w")

    def create_signal_display(self):
        signal_frame = ttk.Frame(self.control_frame)
        signal_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(signal_frame, text="Signal Quality:").pack(anchor="w")
        self.snr_label = ttk.Label(signal_frame, text="SNR: 0.0 dB")
        self.snr_label.pack(anchor="w")
        
        ttk.Label(signal_frame, text="Reception Progress:").pack(anchor="w")
        self.reception_progress = ttk.Progressbar(signal_frame, length=200)
        self.reception_progress.pack(fill=tk.X)

    def create_noaa_content(self):
        # Satellite Position section
        self.sat_pos_frame = ttk.LabelFrame(self.noaa_frame, text="Satellite Position")
        self.sat_pos_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.map_canvas = tk.Canvas(self.sat_pos_frame, bg="#e0e0e0", height=400)
        self.map_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create buttons for TLE Download and Map Update
        btn_frame = ttk.Frame(self.sat_pos_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        download_btn = ttk.Button(btn_frame, text="Download TLE Data")
        download_btn.pack(side=tk.LEFT, padx=5)
        
        update_map_btn = ttk.Button(btn_frame, text="Update Map")
        update_map_btn.pack(side=tk.LEFT, padx=5)
        
        # Satellite Image section
        self.sat_img_frame = ttk.LabelFrame(self.noaa_frame, text="Satellite Image")
        self.sat_img_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.canvas = tk.Canvas(self.sat_img_frame, bg="black", height=400)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.create_text(300, 150, text="Image will appear here", fill="white", font=('Helvetica', 16))

    def create_fm_content(self):
        # FM Stations Table
        self.fm_stations_frame = ttk.LabelFrame(self.fm_frame, text="FM Stations")
        self.fm_stations_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        columns = ('Frequency (MHz)', 'Signal Strength')
        self.fm_stations_tree = ttk.Treeview(self.fm_stations_frame, columns=columns, show='headings')
        for col in columns:
            self.fm_stations_tree.heading(col, text=col)
        self.fm_stations_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Scan Controls
        self.scan_frame = ttk.LabelFrame(self.fm_frame, text="Scan Controls")
        self.scan_frame.pack(fill=tk.X, padx=5, pady=5)
        
        range_frame = ttk.Frame(self.scan_frame)
        range_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(range_frame, text="Start:").pack(side=tk.LEFT, padx=5)
        self.start_freq = ttk.Entry(range_frame, width=8)
        self.start_freq.pack(side=tk.LEFT, padx=5)
        self.start_freq.insert(0, "88.0")
        
        ttk.Label(range_frame, text="End:").pack(side=tk.LEFT, padx=5)
        self.end_freq = ttk.Entry(range_frame, width=8)
        self.end_freq.pack(side=tk.LEFT, padx=5)
        self.end_freq.insert(0, "108.0")
        
        btn_frame = ttk.Frame(self.scan_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        start_scan_btn = ttk.Button(btn_frame, text="Start Scan")
        start_scan_btn.pack(side=tk.LEFT, padx=5)
        
        stop_scan_btn = ttk.Button(btn_frame, text="Stop Scan")
        stop_scan_btn.pack(side=tk.LEFT, padx=5)
        
        save_load_frame = ttk.Frame(self.scan_frame)
        save_load_frame.pack(fill=tk.X, padx=5, pady=5)
        
        save_btn = ttk.Button(save_load_frame, text="Save Stations")
        save_btn.pack(side=tk.LEFT, padx=5)
        
        load_btn = ttk.Button(save_load_frame, text="Load Stations")
        load_btn.pack(side=tk.LEFT, padx=5)
    def start_scan(self):
        """Start scanning police frequencies"""
        if self.scanning:
            return
        
        try:
            # Get scan parameters
            start_freq = float(self.scan_start.get())
            end_freq = float(self.scan_end.get())
            step_khz = float(self.scan_step.get())
            dwell_ms = int(self.scan_dwell.get())
            
            if start_freq >= end_freq:
                raise ValueError("Start frequency must be less than end frequency")
            if step_khz <= 0:
                raise ValueError("Step size must be positive")
            if dwell_ms < 100:
                raise ValueError("Dwell time must be at least 100ms")
            
            # Convert step to MHz
            step_mhz = step_khz / 1000.0
            
            # Initialize scan parameters
            self.scan_frequencies = []
            current_freq = start_freq
            while current_freq <= end_freq:
                self.scan_frequencies.append(current_freq)
                current_freq += step_mhz
            
            self.current_scan_index = 0
            self.scan_active_channels = []
            self.scan_signal_levels = {}
            self.scanning = True
            self.scan_thread_running = True
            
            # Clear active channels list
            for item in self.active_channels_tree.get_children():
                self.active_channels_tree.delete(item)
            
            # Update UI
            self.scan_btn.config(state=tk.DISABLED)
            self.stop_scan_btn.config(state=tk.NORMAL)
            self.scan_status.config(text="Scanning...")
            
            # Start scan thread
            threading.Thread(target=self.run_scan, daemon=True).start()
            
        except ValueError as e:
            self.scan_status.config(text=f"Error: {str(e)}")
            messagebox.showerror("Scan Error", str(e))

    def stop_scan(self):
        """Stop the current scan"""
        self.scan_thread_running = False
        self.scanning = False
        self.scan_status.config(text="Scan stopped")
        self.scan_btn.config(state=tk.NORMAL)
        self.stop_scan_btn.config(state=tk.DISABLED)
        
        # Stop any active reception
        if hasattr(self, 'sdr_process') and self.sdr_process:
            try:
                os.killpg(os.getpgid(self.sdr_process.pid), signal.SIGTERM)
                self.sdr_process.wait(timeout=1)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(os.getpgid(self.sdr_process.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            self.sdr_process = None

    def run_scan(self):
        """Thread that performs the frequency scan"""
        try:
            dwell_ms = int(self.scan_dwell.get())
            min_signal_strength = 20  # Minimum signal strength to consider a channel active
            
            while self.scan_thread_running and self.current_scan_index < len(self.scan_frequencies):
                freq = self.scan_frequencies[self.current_scan_index]
                self.root.after(0, lambda: self.scan_status.config(
                    text=f"Scanning {freq:.3f} MHz ({self.current_scan_index+1}/{len(self.scan_frequencies)})"
                ))
                
                # Set up RTL_FM to check this frequency
                cmd = [
                    "rtl_fm",
                    "-f", f"{freq}e6",
                    "-M", "fm",
                    "-s", "170k",
                    "-l", "0",
                    "-t", "0",  # Don't exit automatically
                    "-"
                ]
                
                try:
                    self.sdr_process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        preexec_fn=os.setsid,
                        bufsize=1024*1024
                    )
                    
                    # Start audio player for this frequency
                    self.police_audio_player.start(freq)
                    
                    # Sample the signal for the dwell time
                    start_time = time.time()
                    signal_samples = []
                    
                    while (time.time() - start_time) < (dwell_ms / 1000.0) and self.scan_thread_running:
                        raw_samples = self.sdr_process.stdout.read(1024)
                        if not raw_samples:
                            break
                        
                        samples = np.frombuffer(raw_samples, dtype=np.uint8).astype(np.float32) / 255.0 - 0.5
                        signal_samples.extend(samples)
                        
                    if signal_samples:
                        # Calculate signal strength (RMS)
                        rms = np.sqrt(np.mean(np.array(signal_samples)**2))
                        signal_strength = min(100, max(0, (rms / 0.3) * 100))  # Scale to 0-100
                        self.scan_signal_levels[freq] = signal_strength
                        
                        # If signal is strong enough, log it as active
                        if signal_strength >= min_signal_strength:
                            timestamp = datetime.now().strftime('%H:%M:%S')
                            if freq not in [ch[0] for ch in self.scan_active_channels]:
                                self.scan_active_channels.append((freq, signal_strength, timestamp))
                                # Update the active channels list in the UI
                                self.root.after(0, self.update_active_channels_list)
                    
                finally:
                    # Clean up the SDR process
                    if hasattr(self, 'sdr_process') and self.sdr_process:
                        try:
                            os.killpg(os.getpgid(self.sdr_process.pid), signal.SIGTERM)
                            self.sdr_process.wait(timeout=0.1)
                        except (ProcessLookupError, subprocess.TimeoutExpired):
                            pass
                        self.sdr_process = None
                    
                    # Stop audio
                    self.police_audio_player.stop()
                    
                    # Move to next frequency if we're still scanning
                    if self.scan_thread_running:
                        self.current_scan_index += 1
                        # If we've reached the end, start over
                        if self.current_scan_index >= len(self.scan_frequencies):
                            self.current_scan_index = 0
                            # Sort active channels by signal strength
                            self.scan_active_channels.sort(key=lambda x: x[1], reverse=True)
                            self.root.after(0, self.update_active_channels_list)
                            # Sleep a bit before starting over
                            time.sleep(1)
        
        except Exception as e:
            self.root.after(0, lambda: self.scan_status.config(text=f"Scan error: {str(e)}"))
        finally:
            self.scan_thread_running = False
            self.scanning = False
            self.root.after(0, lambda: self.scan_status.config(text="Scan stopped"))
            self.root.after(0, lambda: self.scan_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_scan_btn.config(state=tk.DISABLED))

    def update_active_channels_list(self):
        """Update the active channels treeview with current scan results"""
        for item in self.active_channels_tree.get_children():
            self.active_channels_tree.delete(item)
        
        for freq, strength, timestamp in self.scan_active_channels:
            self.active_channels_tree.insert('', 'end', values=(
                f"{freq:.3f}",
                f"{strength:.1f}%",
                timestamp
            ))

    def select_active_channel(self, event):
        """Handle selection of an active channel from the tree"""
        selection = self.active_channels_tree.selection()
        if selection:
            item = self.active_channels_tree.item(selection[0])
            try:
                freq_str = item['values'][0]
                freq = float(freq_str)
                self.freq_entry.delete(0, tk.END)
                self.freq_entry.insert(0, freq_str)
                # Optionally start reception on this frequency
                # if self.scanning:
                #     self.stop_scan()
                #     self.start_audio()
            except (IndexError, ValueError) as e:
                self.scan_status.config(text=f"Invalid frequency: {e}")

    def create_police_content(self):
        # Location selection
        self.location_selection_frame = ttk.Frame(self.police_frame)
        self.location_selection_frame.pack(fill=tk.X, padx=5, pady=5)
        
        location_frame = ttk.LabelFrame(self.location_selection_frame, text="Location")
        location_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Country selection
        country_frame = ttk.Frame(location_frame)
        country_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(country_frame, text="Country:").pack(side=tk.LEFT, padx=5)
        self.country_var = tk.StringVar(value="United States")
        self.country_combo = ttk.Combobox(country_frame, textvariable=self.country_var, state="readonly")
        self.country_combo['values'] = list(self.police_frequencies.keys())
        self.country_combo.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.country_combo.bind("<<ComboboxSelected>>", self.update_states)
        
        # State/Region selection
        state_frame = ttk.Frame(location_frame)
        state_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(state_frame, text="State:").pack(side=tk.LEFT, padx=5)
        self.state_var = tk.StringVar()
        self.state_combo = ttk.Combobox(state_frame, textvariable=self.state_var, state="readonly")
        self.state_combo.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.state_combo.bind("<<ComboboxSelected>>", self.update_cities)
        
        # City selection
        city_frame = ttk.Frame(location_frame)
        city_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(city_frame, text="City:").pack(side=tk.LEFT, padx=5)
        self.city_var = tk.StringVar()
        self.city_combo = ttk.Combobox(city_frame, textvariable=self.city_var, state="readonly")
        self.city_combo.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.city_combo.bind("<<ComboboxSelected>>", self.update_services)
        
        # Service selection
        service_frame = ttk.LabelFrame(self.police_frame, text="Service")
        service_frame.pack(fill=tk.X, padx=5, pady=5)
        
        service_selection = ttk.Frame(service_frame)
        service_selection.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(service_selection, text="Service:").pack(side=tk.LEFT, padx=5)
        self.service_var = tk.StringVar()
        self.service_combo = ttk.Combobox(service_selection, textvariable=self.service_var, state="readonly")
        self.service_combo.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.service_combo.bind("<<ComboboxSelected>>", self.update_police_frequencies)
        
        # Audio processing
        audio_frame = ttk.LabelFrame(self.police_frame, text="Audio Processing")
        audio_frame.pack(fill=tk.X, padx=5, pady=5)
        
        noise_frame = ttk.Frame(audio_frame)
        noise_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(noise_frame, text="Noise Gate:").pack(side=tk.LEFT, padx=5)
        self.noise_gate = ttk.Scale(noise_frame, from_=0, to=100, orient=tk.HORIZONTAL)
        self.noise_gate.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.noise_gate.set(20)  # Start with 20% threshold instead of 50% # Default value
        self.noise_gate.bind("<ButtonRelease-1>", self.update_noise_gate)
        
        self.enable_audio_var = tk.BooleanVar(value=True)
        enable_audio_check = ttk.Checkbutton(audio_frame, text="Enable Audio Processing", 
                                          variable=self.enable_audio_var,
                                          command=self.update_audio_processing)
        enable_audio_check.pack(anchor="w", padx=5, pady=5)

            # Add scan controls after the frequency table
        scan_frame = ttk.LabelFrame(self.police_frame, text="Scan Controls")
        scan_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Scan settings
        settings_frame = ttk.Frame(scan_frame)
        settings_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(settings_frame, text="Step (kHz):").pack(side=tk.LEFT)
        self.scan_step = ttk.Entry(settings_frame, width=6)
        self.scan_step.pack(side=tk.LEFT, padx=5)
        self.scan_step.insert(0, "12.5")  # Default step size for police frequencies
        
        ttk.Label(settings_frame, text="Dwell (ms):").pack(side=tk.LEFT)
        self.scan_dwell = ttk.Entry(settings_frame, width=6)
        self.scan_dwell.pack(side=tk.LEFT, padx=5)
        self.scan_dwell.insert(0, "500")  # Default dwell time
        
        # Scan range
        range_frame = ttk.Frame(scan_frame)
        range_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(range_frame, text="Start (MHz):").pack(side=tk.LEFT)
        self.scan_start = ttk.Entry(range_frame, width=8)
        self.scan_start.pack(side=tk.LEFT, padx=5)
        self.scan_start.insert(0, "450.000")
        
        ttk.Label(range_frame, text="End (MHz):").pack(side=tk.LEFT)
        self.scan_end = ttk.Entry(range_frame, width=8)
        self.scan_end.pack(side=tk.LEFT, padx=5)
        self.scan_end.insert(0, "470.000")
        
        # Scan buttons
        btn_frame = ttk.Frame(scan_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.scan_btn = ttk.Button(btn_frame, text="Start Scan", command=self.start_scan)
        self.scan_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_scan_btn = ttk.Button(btn_frame, text="Stop Scan", 
                                    command=self.stop_scan, state=tk.DISABLED)
        self.stop_scan_btn.pack(side=tk.LEFT, padx=5)
        
        # Scan status
        self.scan_status = ttk.Label(scan_frame, text="Scan stopped")
        self.scan_status.pack(anchor="w", padx=5, pady=5)
        
        # Active channels list
        self.active_channels_frame = ttk.LabelFrame(self.police_frame, text="Active Channels")
        self.active_channels_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        columns = ('Frequency (MHz)', 'Signal Strength', 'Timestamp')
        self.active_channels_tree = ttk.Treeview(
            self.active_channels_frame, 
            columns=columns, 
            show='headings'
        )
        for col in columns:
            self.active_channels_tree.heading(col, text=col)
        self.active_channels_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.active_channels_tree.bind("<Double-1>", self.select_active_channel)
        
        # Frequency table
        self.frequency_table_frame = ttk.Frame(self.police_frame)
        self.frequency_table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        columns = ('Frequency (MHz)', 'Description')
        self.frequency_tree = ttk.Treeview(self.frequency_table_frame, columns=columns, show='headings')
        for col in columns:
            self.frequency_tree.heading(col, text=col)
            self.frequency_tree.column(col, width=150)
        self.frequency_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.frequency_tree.bind("<Double-1>", self.select_police_frequency)
        
        # Available frequencies list
        self.avail_freq_frame = ttk.LabelFrame(self.control_frame, text="Location Selection")
        self.avail_freq_label = ttk.Label(self.avail_freq_frame, text="Available Frequencies:")
        self.avail_freq_label.pack(anchor="w", padx=5, pady=5)
        
        self.freq_listbox = tk.Listbox(self.avail_freq_frame, height=8)
        self.freq_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.freq_listbox.bind("<Double-1>", self.select_frequency_from_list)
        
        self.status_label = ttk.Label(self.avail_freq_frame, text="")
        self.status_label.pack(anchor="w", padx=5, pady=5)
        
        # Initial population of states
        self.update_states()

    def create_airport_content(self):
        """Create the airport tower mode interface with real-time radar map"""
        # Location selection frame
        self.airport_location_frame = ttk.Frame(self.airport_frame)
        self.airport_location_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Location selection components
        location_frame = ttk.LabelFrame(self.airport_location_frame, text="Location")
        location_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Country selection
        country_frame = ttk.Frame(location_frame)
        country_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(country_frame, text="Country:").pack(side=tk.LEFT, padx=5)
        self.airport_country_var = tk.StringVar(value="United States")
        self.airport_country_combo = ttk.Combobox(
            country_frame, 
            textvariable=self.airport_country_var, 
            state="readonly"
        )
        self.airport_country_combo['values'] = list(self.airport_frequencies.keys())
        self.airport_country_combo.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.airport_country_combo.bind("<<ComboboxSelected>>", self.update_airport_states)
        
        # State selection
        state_frame = ttk.Frame(location_frame)
        state_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(state_frame, text="State:").pack(side=tk.LEFT, padx=5)
        self.airport_state_var = tk.StringVar()
        self.airport_state_combo = ttk.Combobox(
            state_frame, 
            textvariable=self.airport_state_var, 
            state="readonly"
        )
        self.airport_state_combo.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.airport_state_combo.bind("<<ComboboxSelected>>", self.update_airport_airports)
        
        # Airport selection
        airport_frame = ttk.Frame(location_frame)
        airport_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(airport_frame, text="Airport:").pack(side=tk.LEFT, padx=5)
        self.airport_var = tk.StringVar()
        self.airport_combo = ttk.Combobox(
            airport_frame, 
            textvariable=self.airport_var, 
            state="readonly"
        )
        self.airport_combo.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.airport_combo.bind("<<ComboboxSelected>>", self.update_airport_services)
        
        # Service selection
        service_frame = ttk.LabelFrame(self.airport_frame, text="Service")
        service_frame.pack(fill=tk.X, padx=5, pady=5)
        
        service_selection = ttk.Frame(service_frame)
        service_selection.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(service_selection, text="Service:").pack(side=tk.LEFT, padx=5)
        self.airport_service_var = tk.StringVar()
        self.airport_service_combo = ttk.Combobox(
            service_selection, 
            textvariable=self.airport_service_var, 
            state="readonly"
        )
        self.airport_service_combo.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.airport_service_combo.bind("<<ComboboxSelected>>", self.update_airport_frequencies)
        
        # Audio processing controls
        audio_frame = ttk.LabelFrame(self.airport_frame, text="Audio Processing")
        audio_frame.pack(fill=tk.X, padx=5, pady=5)
        
        noise_frame = ttk.Frame(audio_frame)
        noise_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(noise_frame, text="Noise Gate:").pack(side=tk.LEFT, padx=5)
        self.airport_noise_gate = ttk.Scale(
            noise_frame, 
            from_=0, 
            to=100, 
            orient=tk.HORIZONTAL
        )
        self.airport_noise_gate.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.airport_noise_gate.set(20)  # Default value
        self.airport_noise_gate.bind("<ButtonRelease-1>", self.update_airport_noise_gate)
        
        self.enable_airport_audio_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            audio_frame, 
            text="Enable Audio Processing", 
            variable=self.enable_airport_audio_var,
            command=self.update_airport_audio_processing
        ).pack(anchor=tk.W, padx=5, pady=5)
        
        # Frequency table
        self.airport_frequency_table_frame = ttk.Frame(self.airport_frame)
        self.airport_frequency_table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        columns = ('Frequency (MHz)', 'Description')
        self.airport_frequency_tree = ttk.Treeview(
            self.airport_frequency_table_frame, 
            columns=columns, 
            show='headings'
        )
        for col in columns:
            self.airport_frequency_tree.heading(col, text=col)
            self.airport_frequency_tree.column(col, width=150)
        self.airport_frequency_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.airport_frequency_tree.bind("<Double-1>", self.select_airport_frequency)
        
        # Radar map display
        self.airport_map_frame = ttk.LabelFrame(self.airport_frame, text="Airport Radar")
        self.airport_map_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create canvas for the map
        self.airport_map_canvas = tk.Canvas(
            self.airport_map_frame, 
            bg='white', 
            height=500
        )
        self.airport_map_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Map controls
        map_controls = ttk.Frame(self.airport_map_frame)
        map_controls.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(
            map_controls, 
            text="Refresh Map", 
            command=self.update_airport_map
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            map_controls, 
            text="Clear Aircraft", 
            command=self.clear_aircraft_tracks
        ).pack(side=tk.LEFT, padx=5)
        
        self.auto_update_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            map_controls, 
            text="Auto-Update", 
            variable=self.auto_update_var
        ).pack(side=tk.LEFT, padx=5)
        
        # Radar settings
        settings_frame = ttk.LabelFrame(self.airport_frame, text="Radar Settings")
        settings_frame.pack(fill=tk.X, padx=5, pady=5)
        
        range_frame = ttk.Frame(settings_frame)
        range_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(range_frame, text="Range (km):").pack(side=tk.LEFT, padx=5)
        self.radar_range = ttk.Scale(
            range_frame, 
            from_=10, 
            to=200, 
            value=50
        )
        self.radar_range.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.range_value = ttk.Label(range_frame, text="50 km")
        self.range_value.pack(side=tk.LEFT, padx=5)
        self.radar_range.config(command=lambda v: self.range_value.config(
            text=f"{float(v):.0f} km"
        ))
        
        # Initialize map and tracking
        self.airport_tower = None
        self.aircraft = {}
        self.map_image = None
        self.map_photo = None
        self.create_initial_airport_map()
        
        # Start map update thread
        self.map_thread_running = True
        Thread(target=self.map_update_thread, daemon=True).start()

    def update_states(self, event=None):
        """Update states/regions based on selected country"""
        country = self.country_var.get()
        
        if country in self.police_frequencies:
            # Get states/regions for the selected country
            states = list(self.police_frequencies[country].keys())
            self.state_combo['values'] = states
            
            if states:
                self.state_combo.current(0)
                self.update_cities()
                self.status_label.config(text="")
            else:
                self.state_combo.set('')
                self.status_label.config(text=f"No states found for {country}")
        else:
            self.state_combo['values'] = []
            self.state_combo.set('')
            self.status_label.config(text=f"No states found for {country}")
            
        # Clear dependent dropdowns
        self.city_combo['values'] = []
        self.city_combo.set('')
        self.service_combo['values'] = []
        self.service_combo.set('')
        self.clear_frequency_display()

    def update_cities(self, event=None):
        """Update cities based on selected state/region"""
        country = self.country_var.get()
        state = self.state_var.get()
        
        if country in self.police_frequencies and state in self.police_frequencies[country]:
            # Get cities for the selected state
            cities = list(self.police_frequencies[country][state].keys())
            self.city_combo['values'] = cities
            
            if cities:
                self.city_combo.current(0)
                self.update_services()
                self.status_label.config(text="")
            else:
                self.city_combo.set('')
                self.status_label.config(text=f"No cities found for {state}")
        else:
            self.city_combo['values'] = []
            self.city_combo.set('')
            self.status_label.config(text=f"No cities found for {state}")
            
        # Clear dependent dropdowns
        self.service_combo['values'] = []
        self.service_combo.set('')
        self.clear_frequency_display()

    def update_services(self, event=None):
        """Update services based on selected city"""
        country = self.country_var.get()
        state = self.state_var.get()
        city = self.city_var.get()
        
        if (country in self.police_frequencies and 
            state in self.police_frequencies[country] and 
            city in self.police_frequencies[country][state]):
            
            # Get services for the selected city
            services = list(self.police_frequencies[country][state][city].keys())
            self.service_combo['values'] = services
            
            if services:
                self.service_combo.current(0)
                self.update_police_frequencies()
                self.status_label.config(text="")
            else:
                self.service_combo.set('')
                self.status_label.config(text=f"No services found for {city}")
        else:
            self.service_combo['values'] = []
            self.service_combo.set('')
            self.status_label.config(text=f"No services found for {city}")
        
        self.clear_frequency_display()

    def update_police_frequencies(self, event=None):
        """Update police frequencies based on selected service"""
        country = self.country_var.get()
        state = self.state_var.get()
        city = self.city_var.get()
        service = self.service_var.get()
        
        # Clear existing items
        self.clear_frequency_display()
        
        if not all([country, state, city, service]):
            return
            
        try:
            # Access the frequencies list for this service
            frequencies_list = self.police_frequencies[country][state][city][service]
            
            # Process frequencies
            for freq_entry in frequencies_list:
                parts = freq_entry.split(' - ', 1)
                freq_str = parts[0].strip()
                desc = parts[1] if len(parts) > 1 else service
                
                # Remove MHz at the end if present for the frequency tree
                if freq_str.endswith(" MHz"):
                    freq_value = freq_str[:-4]
                else:
                    freq_value = freq_str
                
                # Add to treeview
                self.frequency_tree.insert('', 'end', values=(freq_value, desc))
                
                # Add to listbox (just the frequency value)
                self.freq_listbox.insert(tk.END, freq_value)
                
            self.status_label.config(text=f"Found {len(frequencies_list)} frequencies for {service}")
            
        except (KeyError, Exception) as e:
            self.status_label.config(text=f"Error loading frequencies: {e}")

    def select_police_frequency(self, event):
        """Handle selection of a frequency from the treeview"""
        selection = self.frequency_tree.selection()
        if selection:
            item = self.frequency_tree.item(selection[0])
            try:
                freq = item['values'][0]
                # Ensure the frequency is a valid number
                float(freq)  # This will raise ValueError if not convertible to float
                self.freq_entry.delete(0, tk.END)
                self.freq_entry.insert(0, freq)
            except (IndexError, ValueError) as e:
                self.status_label.config(text=f"Invalid frequency format: {e}")

    def select_frequency_from_list(self, event):
        """Handle selection of a frequency from the listbox"""
        selection = self.freq_listbox.curselection()
        if selection:
            try:
                freq = self.freq_listbox.get(selection[0])
                # Ensure the frequency is a valid number
                float(freq)  # This will raise ValueError if not convertible to float
                self.freq_entry.delete(0, tk.END)
                self.freq_entry.insert(0, freq)
            except (IndexError, ValueError) as e:
                self.status_label.config(text=f"Invalid frequency format: {e}")

    def update_noise_gate(self, event=None):
        """Update noise gate level for police audio"""
        level = self.noise_gate.get()
        self.police_audio_player.set_noise_gate(level)

    def update_audio_processing(self):
        """Enable/disable audio processing for police audio"""
        enabled = self.enable_audio_var.get()
        self.police_audio_player.set_processing_enabled(enabled)

    def update_controls(self):
        mode = self.mode_var.get()
        
        for frame in [self.noaa_frame, self.fm_frame, self.police_frame, self.airport_frame]:
            frame.pack_forget()
    
        # Hide specialized buttons
        self.decode_btn.pack_forget()
        self.duration_frame.pack_forget()
        self.audio_btn_frame.pack_forget()
        self.avail_freq_frame.pack_forget()
        self.airport_avail_freq_frame.pack_forget()
        
        # Show the correct UI for the selected mode
        if mode == "noaa" or mode == "goes":
            self.noaa_frame.pack(fill=tk.BOTH, expand=True)
            self.duration_frame.pack(fill=tk.X, pady=5)
            self.decode_btn.pack(fill=tk.X, pady=5)
            
            # Set appropriate defaults for the mode
            if mode == "noaa":
                self.freq_entry.delete(0, tk.END)
                self.freq_entry.insert(0, "137.5")
                self.play_btn.config(text="▶ Start Reception")
                self.stop_btn.config(text="■ Stop Reception")
            else:  # GOES
                self.freq_entry.delete(0, tk.END)
                self.freq_entry.insert(0, "1694.1")
                self.play_btn.config(text="▶ Start Reception")
                self.stop_btn.config(text="■ Stop Reception")
                
        elif mode == "fm":
            self.fm_frame.pack(fill=tk.BOTH, expand=True)
            self.freq_entry.delete(0, tk.END)
            self.freq_entry.insert(0, "104.3")
            self.play_btn.config(text="▶ Start Reception")
            self.stop_btn.config(text="■ Stop Reception")
            
        if mode == "police":
            self.police_frame.pack(fill=tk.BOTH, expand=True)
            self.audio_btn_frame.pack(fill=tk.X, pady=5)
            self.avail_freq_frame.pack(fill=tk.X, pady=5)
            self.freq_entry.delete(0, tk.END)
            if self.scan_active_channels:
                # Default to first active channel if available
                self.freq_entry.insert(0, f"{self.scan_active_channels[0][0]:.3f}")
            else:
                self.freq_entry.insert(0, "460.500")
            self.play_btn.config(text="▶ Start Reception")
            self.stop_btn.config(text="■ Stop Reception")
            
        elif mode == "airport":
            self.airport_frame.pack(fill=tk.BOTH, expand=True)
            self.audio_btn_frame.pack(fill=tk.X, pady=5)
            self.airport_avail_freq_frame.pack(fill=tk.X, pady=5)
            self.freq_entry.delete(0, tk.END)
            self.freq_entry.insert(0, "118.000")
            self.play_btn.config(text="▶ Start Reception")
            self.stop_btn.config(text="■ Stop Reception")

    def start_audio(self):
        """Start audio for police/services mode"""
        if self.running:
            return
            
        try:
            freq_str = self.freq_entry.get()
            
            # Ensure frequency is a valid number
            try:
                freq = float(freq_str)
            except ValueError:
                raise ValueError(f"Invalid frequency format: '{freq_str}'. Please enter a valid number.")
            
            self.show_status(f"Starting audio on {freq}MHz...")
            
            # Police-specific setup
            cmd = [
                "rtl_fm", 
                "-f", f"{freq}e6", 
                "-M", "fm",
                "-s", "170k",  # Sample rate
                "-r", "32k",   # Output rate
                "-l", "0",     # Disable squelch
                "-E", "deemp"  # Enable de-emphasis (improves FM voice quality)
                "-"
                ]
            self.sdr_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,
                bufsize=1024*1024
            )
            self.police_audio_player.start(freq)  # Use police audio player
            self.running = True
            
            # Start processing thread for police audio
            threading.Thread(target=self.read_police_audio, daemon=True).start()
            
            # Update button states
            self.start_audio_btn.config(state=tk.DISABLED)
            self.stop_audio_btn.config(state=tk.NORMAL)
            
            self.show_status(f"Audio started on {freq}MHz")
            
        except Exception as e:
            self.show_status(f"Error: {str(e)}", 5000)
            messagebox.showerror("Error", f"Failed to start audio: {str(e)}")

    def stop_audio(self):
        """Stop audio for police/services mode"""
        if not self.running:
            return
        
        self.show_status("Stopping audio...")
        
        try:
            # Stop audio first
            self.police_audio_player.stop()
            
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
        
        # Update button states
        self.start_audio_btn.config(state=tk.NORMAL)
        self.stop_audio_btn.config(state=tk.DISABLED)
        
        self.show_status("Audio stopped")

    def read_police_audio(self):
        """Read audio data from SDR process for police/services mode"""
        try:
            chunk_size = 1024 * 4
            
            while self.running and self.sdr_process:
                raw_samples = self.sdr_process.stdout.read(chunk_size)
                if not raw_samples:
                    break
                
                # Send to police audio player
                self.police_audio_player.play(raw_samples)
                        
        except Exception as e:
            self.show_status(f"Read error: {e}", 5000)
        finally:
            if self.running:
                self.root.after(0, self.stop_audio)

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
                    "-s", "250k", 
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
                    
                    # Always put image in queue if we have one
                    if image is not None:
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
                # Get all available images from queue
                while True:
                    image = self.image_queue.get_nowait()
                    if image:
                        canvas_width = self.canvas.winfo_width()
                        canvas_height = self.canvas.winfo_height()
                        
                        if canvas_width > 0 and canvas_height > 0:
                            # Maintain aspect ratio
                            img_ratio = image.width / image.height
                            canvas_ratio = canvas_width / canvas_height
                            
                            if canvas_ratio > img_ratio:
                                display_height = canvas_height
                                display_width = int(canvas_height * img_ratio)
                            else:
                                display_width = canvas_width
                                display_height = int(canvas_width / img_ratio)
                            
                            # Resize if needed
                            if display_width != image.width or display_height != image.height:
                                display_image = image.resize((display_width, display_height), 
                                                        Image.Resampling.LANCZOS)
                            else:
                                display_image = image
                            
                            # Update display
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
        
        # Schedule next update
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
        """Clean up resources when closing the app"""
        self.signal_running = False
        self.map_thread_running = False
        self.stop_reception()
        self.stop_scan()
        self.stop_airport_audio()
        time.sleep(0.5)  # Give threads time to exit
        self.root.destroy()

    def toggle_decoding(self):
        """Toggle the decoding process on/off"""
        if not self.running:
            messagebox.showwarning("Warning", "Please start reception first")
            return
        
        self.decoding_active = not self.decoding_active
        
        if self.decoding_active:
            self.decode_btn.config(text="■ Stop Decoding")
            self.show_status("Decoding started - displaying images")
            # Force immediate display update
            self.update_display()
        else:
            self.decode_btn.config(text="▶ Start Decoding")
            self.show_status("Decoding stopped", 3000)

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

    def setup_decoders(self):
        """Initialize decoders and sample queues"""
        self.noaa_decoder = NOAADecoder()
        self.goes_decoder = GOESDecoder()
        self.sample_queue = queue.Queue(maxsize=100)
        self.image_queue = queue.Queue(maxsize=10)
        self.snr_queue = queue.Queue()

    def setup_signal_monitor(self):
        """Set up and start the signal monitoring thread"""
        self.signal_running = True
        self.signal_data = []
        threading.Thread(target=self.monitor_signals, daemon=True).start()

    def setup_satellite_tracker(self):
        """Initialize the satellite tracker and update passes display"""
        self.tracker = SatelliteTracker()
        
        # Add a passes tree to the NOAA display that was missing
        self.passes_frame = ttk.Frame(self.noaa_frame)
        self.passes_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.passes_tree = ttk.Treeview(self.passes_frame, columns=('Satellite', 'Time', 'Duration', 'Max Elev'), show='headings')
        for col in ['Satellite', 'Time', 'Duration', 'Max Elev']:
            self.passes_tree.heading(col, text=col)
        self.passes_tree.pack(fill=tk.BOTH, expand=True)
        
        self.update_next_passes()

    def monitor_signals(self):
        """Monitor signal quality and update displays"""
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
        """Update signal quality displays with current SNR"""
        snr = max(0, min(30, self.current_snr))
        self.snr_label.config(text=f"SNR: {snr:.1f} dB")

    def clear_frequency_display(self):
        """Clear the frequency displays"""
        for item in self.frequency_tree.get_children():
            self.frequency_tree.delete(item)
        self.freq_listbox.delete(0, tk.END)

    def update_airport_states(self, event=None):
        """Update states/regions based on selected country for airport towers"""
        country = self.airport_country_var.get()
        
        if country in self.airport_frequencies:
            # Get states/regions for the selected country
            states = list(self.airport_frequencies[country].keys())
            self.airport_state_combo['values'] = states
            
            if states:
                self.airport_state_combo.current(0)
                self.update_airport_airports()
                self.airport_status_label.config(text="")
            else:
                self.airport_state_combo.set('')
                self.airport_status_label.config(text=f"No states found for {country}")
        else:
            self.airport_state_combo['values'] = []
            self.airport_state_combo.set('')
            self.airport_status_label.config(text=f"No states found for {country}")
            
        # Clear dependent dropdowns
        self.airport_combo['values'] = []
        self.airport_combo.set('')
        self.airport_service_combo['values'] = []
        self.airport_service_combo.set('')
        self.clear_airport_frequency_display()

    def update_airport_airports(self, event=None):
        """Update airports based on selected state/region"""
        country = self.airport_country_var.get()
        state = self.airport_state_var.get()
        
        if country in self.airport_frequencies and state in self.airport_frequencies[country]:
            # Get airports for the selected state
            airports = list(self.airport_frequencies[country][state].keys())
            self.airport_combo['values'] = airports
            
            if airports:
                self.airport_combo.current(0)
                self.update_airport_services()
                self.airport_status_label.config(text="")
            else:
                self.airport_combo.set('')
                self.airport_status_label.config(text=f"No airports found for {state}")
        else:
            self.airport_combo['values'] = []
            self.airport_combo.set('')
            self.airport_status_label.config(text=f"No airports found for {state}")
            
        # Clear dependent dropdowns
        self.airport_service_combo['values'] = []
        self.airport_service_combo.set('')
        self.clear_airport_frequency_display()

    def update_airport_services(self, event=None):
        """Update services based on selected airport"""
        country = self.airport_country_var.get()
        state = self.airport_state_var.get()
        airport = self.airport_var.get()
        
        if (country in self.airport_frequencies and 
            state in self.airport_frequencies[country] and 
            airport in self.airport_frequencies[country][state]):
            
            # Get services for the selected airport
            services = list(self.airport_frequencies[country][state][airport].keys())
            self.airport_service_combo['values'] = services
            
            if services:
                self.airport_service_combo.current(0)
                self.update_airport_frequencies()
                self.airport_status_label.config(text="")
            else:
                self.airport_service_combo.set('')
                self.airport_status_label.config(text=f"No services found for {airport}")
        else:
            self.airport_service_combo['values'] = []
            self.airport_service_combo.set('')
            self.airport_status_label.config(text=f"No services found for {airport}")
        
        self.clear_airport_frequency_display()

    def update_airport_frequencies(self, event=None):
        """Update airport frequencies based on selected service"""
        country = self.airport_country_var.get()
        state = self.airport_state_var.get()
        airport = self.airport_var.get()
        service = self.airport_service_var.get()
        
        # Clear existing items
        self.clear_airport_frequency_display()
        
        if not all([country, state, airport, service]):
            return
            
        try:
            # Access the frequencies list for this service
            frequencies_list = self.airport_frequencies[country][state][airport][service]
            
            # Process frequencies
            for freq_entry in frequencies_list:
                parts = freq_entry.split(' - ', 1)
                freq_str = parts[0].strip()
                desc = parts[1] if len(parts) > 1 else service
                
                # Remove MHz at the end if present for the frequency tree
                if freq_str.endswith(" MHz"):
                    freq_value = freq_str[:-4]
                else:
                    freq_value = freq_str
                
                # Add to treeview
                self.airport_frequency_tree.insert('', 'end', values=(freq_value, desc))
                
                # Add to listbox (just the frequency value)
                self.airport_freq_listbox.insert(tk.END, freq_value)
                
            self.airport_status_label.config(text=f"Found {len(frequencies_list)} frequencies for {service}")
            
        except (KeyError, Exception) as e:
            self.airport_status_label.config(text=f"Error loading frequencies: {e}")

    def select_airport_frequency(self, event):
        """Handle selection of a frequency from the airport treeview"""
        selection = self.airport_frequency_tree.selection()
        if selection:
            item = self.airport_frequency_tree.item(selection[0])
            try:
                freq = item['values'][0]
                # Ensure the frequency is a valid number
                float(freq)  # This will raise ValueError if not convertible to float
                self.freq_entry.delete(0, tk.END)
                self.freq_entry.insert(0, freq)
            except (IndexError, ValueError) as e:
                self.airport_status_label.config(text=f"Invalid frequency format: {e}")

    def select_airport_frequency_from_list(self, event):
        """Handle selection of a frequency from the airport listbox"""
        selection = self.airport_freq_listbox.curselection()
        if selection:
            try:
                freq = self.airport_freq_listbox.get(selection[0])
                # Ensure the frequency is a valid number
                float(freq)  # This will raise ValueError if not convertible to float
                self.freq_entry.delete(0, tk.END)
                self.freq_entry.insert(0, freq)
            except (IndexError, ValueError) as e:
                self.airport_status_label.config(text=f"Invalid frequency format: {e}")

    def update_airport_noise_gate(self, event=None):
        """Update noise gate level for airport audio"""
        level = self.airport_noise_gate.get()
        self.police_audio_player.set_noise_gate(level)  # Reuse police audio player

    def update_airport_audio_processing(self):
        """Enable/disable audio processing for airport audio"""
        enabled = self.enable_airport_audio_var.get()
        self.police_audio_player.set_processing_enabled(enabled)  # Reuse police audio player

    def clear_airport_frequency_display(self):

        """Clear the airport frequency displays"""
        for item in self.airport_frequency_tree.get_children():
            self.airport_frequency_tree.delete(item)
        self.airport_freq_listbox.delete(0, tk.END)

    def create_initial_airport_map(self):
        """Create the initial airport map with default location"""
        # Default to New York coordinates if no airport selected
        if not hasattr(self, 'airport_tower') or self.airport_tower is None:
            lat, lon = 40.7128, -74.0060
        else:
            lat, lon = self.airport_tower.lat, self.airport_tower.lon
        
        # Create a folium map
        self.airport_map = folium.Map(
            location=[lat, lon],
            zoom_start=12,
            tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            attr='OpenStreetMap'
        )
        
        # Add marker cluster
        self.marker_cluster = MarkerCluster().add_to(self.airport_map)
        
        # Update the display
        self.update_airport_map_display()

    def update_airport_map_display(self):
        """Update the Tkinter canvas with the current folium map"""
        if not hasattr(self, 'airport_map'):
            return
            
        # Save the map to a temporary HTML file
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as tmp:
            self.airport_map.save(tmp.name)
            tmp_path = tmp.name
        
        # Use selenium to capture a screenshot of the map if available
        try:
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=800,600')
            driver = webdriver.Chrome(options=options)
            driver.get(f'file://{tmp_path}')
            time.sleep(1)  # Wait for map to load
            png = driver.get_screenshot_as_png()
            driver.quit()
        except Exception as e:
            print(f"Error capturing map with Selenium: {e}")
            # Fallback to a blank map if ChromeDriver isn't available
            img = Image.new('RGB', 
                        (self.airport_map_canvas.winfo_width(), 
                            self.airport_map_canvas.winfo_height()), 
                        color='white')
            draw = ImageDraw.Draw(img)
            draw.text((100, 100), 
                    "Map display requires ChromeDriver\nInstall with: brew install --cask chromedriver", 
                    fill="black", 
                    font=ImageFont.load_default())
            png = img.tobytes()
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass
        
        # Convert screenshot to PhotoImage
        try:
            img = Image.open(BytesIO(png))
            img = img.resize(
                (self.airport_map_canvas.winfo_width(), 
                self.airport_map_canvas.winfo_height()),
                Image.Resampling.LANCZOS  # Correct resampling method
            )
        except Exception as e:
            print(f"Error processing map image: {e}")
            return
        
        # Update the canvas
        if hasattr(self, 'map_photo'):
            self.airport_map_canvas.delete(self.map_image)
        
        self.map_photo = ImageTk.PhotoImage(img)
        self.map_image = self.airport_map_canvas.create_image(
            self.airport_map_canvas.winfo_width() // 2,
            self.airport_map_canvas.winfo_height() // 2,
            image=self.map_photo
        )


    


    def update_airport_map(self):
        """Update the airport map with current aircraft positions"""
        if not hasattr(self, 'airport_tower') or self.airport_tower is None:
            return
        
        # Clear existing markers
        self.marker_cluster.clear_markers()
        
        # Add tower marker
        folium.Marker(
            [self.airport_tower.lat, self.airport_tower.lon],
            popup=f"<b>{self.airport_tower.name}</b><br>"
                f"Frequency: {self.airport_tower.frequency} MHz",
            icon=folium.Icon(color='red', icon='tower-cell')
        ).add_to(self.marker_cluster)
        
        # Add aircraft markers
        for icao, aircraft in self.aircraft.items():
            if not aircraft.positions:
                continue
                
            # Get latest position
            lat, lon, alt, _ = aircraft.positions[-1]
            
            # Create popup content
            popup_content = (f"<b>{aircraft.callsign if aircraft.callsign else icao}</b><br>"
                            f"Altitude: {alt} ft<br>"
                            f"Speed: {aircraft.speed * 1.94384:.1f} kt<br>"
                            f"Heading: {aircraft.heading:.0f}°<br>"
                            f"Signal: {aircraft.signal_strength:.1f}%")
            
            # Create marker with custom icon
            icon_color = 'green' if aircraft.signal_strength > 50 else 'orange' if aircraft.signal_strength > 25 else 'red'
            icon = folium.Icon(
                color=icon_color,
                icon='plane',
                angle=aircraft.heading  # Rotate plane icon to match heading
            )
            
            # Add marker
            folium.Marker(
                [lat, lon],
                popup=popup_content,
                icon=icon
            ).add_to(self.marker_cluster)
            
            # Add flight path if enabled
            if self.show_paths_var.get() and len(aircraft.positions) > 1:
                path_coords = [[p[0], p[1]] for p in aircraft.positions]
                folium.PolyLine(
                    path_coords,
                    color=icon_color,
                    weight=1.5,
                    opacity=0.7
                ).add_to(self.airport_map)
        
        # Add radar range circle
        folium.Circle(
            radius=self.radar_range.get() * 1000,  # Convert to meters
            location=[self.airport_tower.lat, self.airport_tower.lon],
            color='blue',
            fill=True,
            fill_color='blue',
            fill_opacity=0.1,
            weight=1
        ).add_to(self.airport_map)
        
        # Update the display
        self.update_airport_map_display()

    def update_airport_map_display(self):
        """Update the Tkinter canvas with the current folium map"""
        if not hasattr(self, 'airport_map'):
            return
            
        # Save the map to a temporary HTML file
        with tempfile.NamedTemporaryFile(suffix='.html', delete=  False) as tmp:
            self.airport_map.save(tmp.name)
            tmp_path =  tmp.name
        
        # Use selenium to capture a  screenshot  if  available
        img =  None
        try:
            options =  Options()
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=800,600')
            driver =  webdriver.Chrome(options=options)
            driver.get(f'file://{  tmp_path  }')
            time.sleep(1)  # Wait  for  map  to  load
            png =  driver.get_screenshot_as_png()
            driver.quit()
            img =  Image.open(BytesIO(png))
        except  WebDriverException as  e:
            print(f"ChromeDriver  not  available,  using  fallback  image")
            # Create  a  simple  fallback  image
            img =  Image.new('RGB',  (800,  600),  color='white')
            draw =  ImageDraw.Draw(img)
            draw.text((100,  100),  
                    "Map  display  requires  ChromeDriver\n"
                    "Install  with:  brew  install  --  cask  chromedriver",
                    fill="black")
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass
        
        if  img:
            try:
                # Resize  to  fit  canvas
                canvas_width =  self.airport_map_canvas.winfo_width()
                canvas_height =  self.airport_map_canvas.winfo_height()
                
                if  canvas_width  >  0  and  canvas_height  >  0:
                    img =  img.resize(
                        (canvas_width,  canvas_height),
                        Image.Resampling.LANCZOS  #  Fixed  resampling  method
                    )
                    
                    #  Update  canvas
                    if  hasattr(self,  'map_photo'):
                        self.airport_map_canvas.delete(self.map_image)
                    
                    self.map_photo =  ImageTk.PhotoImage(img)
                    self.map_image =  self.airport_map_canvas.create_image(
                        canvas_width  //  2,
                        canvas_height  //  2,
                        image=self.map_photo
                    )
            except  Exception as  e:
                print(f"Error  updating  map  display:  {  e  }")

    def map_update_thread(self):
        """Thread to periodically update the map"""
        while getattr(self, 'map_thread_running', True):
            try:
                if (getattr(self, 'auto_update_var',  None) and 
                    getattr(self, 'auto_update_var').get() and 
                    hasattr(self, 'airport_tower')):
                    self.root.after(0, self.update_airport_map)
                time.sleep(5)
            except Exception as e:
                print(f"Map  update  error:  {  e  }")
                break


    def  clear_aircraft_tracks(self):
        """Clear  all  aircraft  tracks  from  the  map"""
        if  hasattr(self,  'aircraft'):
            self.aircraft =  {}
        if  hasattr(self,  'airport_tower')  and  hasattr(self.airport_tower,  'aircraft'):
            self.airport_tower.aircraft =  {}
        if  hasattr(self,  'update_airport_map'):
            self.update_airport_map()

    def process_airport_audio(self, data):
        """Process audio data from airport tower to detect and track aircraft"""
        if not hasattr(self, 'airport_tower') or not self.airport_tower:
            return
        
        try:
            # Convert audio to numpy array
            samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Calculate signal strength
            rms = np.sqrt(np.mean(samples**2))
            signal_strength = min(100, max(0, (rms / 0.3) * 100))
            
            # Simple aircraft detection - in a real app you'd decode ADS-B or other protocols
            if signal_strength > 20:  # Threshold for aircraft detection
                # Generate a fake position for demo purposes
                # In a real app you'd get this from decoded signals
                icao_id = "DEMO" + str(len(self.aircraft) + 1).zfill(3)
                if icao_id not in self.aircraft:
                    self.aircraft[icao_id] = Aircraft(icao_id, callsign="FLT" + icao_id)
                
                # Calculate position relative to tower
                bearing = 2 * math.pi * time.time() / 60  # Rotate over 60 seconds
                distance = 0.5 * self.radar_range.get()  # 50% of radar range
                lat, lon = self.calculate_position(
                    self.airport_tower.lat, 
                    self.airport_tower.lon,
                    distance, 
                    math.degrees(bearing)
                )
                alt = 10000 + 5000 * math.sin(time.time() / 20)  # Vary altitude
                
                # Update aircraft position
                self.aircraft[icao_id].update_position(
                    lat, lon, 
                    int(alt), 
                    datetime.now(),
                    signal_strength
                )
                
                # If auto-update is on, trigger map update
                if self.auto_update_var.get():
                    self.root.after(0, self.update_airport_map)
        
        except Exception as e:
            print(f"Error processing airport audio: {e}")

    def calculate_position(self, lat, lon, distance_km, bearing_deg):
        """
        Calculate new position given a starting point, distance and bearing
        Returns (new_lat, new_lon)
        """
        R = 6371  # Earth's radius in km
        bearing = math.radians(bearing_deg)
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        
        new_lat = math.asin(
            math.sin(lat_rad) * math.cos(distance_km/R) +
            math.cos(lat_rad) * math.sin(distance_km/R) * math.cos(bearing)
        )
        
        new_lon = lon_rad + math.atan2(
            math.sin(bearing) * math.sin(distance_km/R) * math.cos(lat_rad),
            math.cos(distance_km/R) - math.sin(lat_rad) * math.sin(new_lat)
        )
        
        return (math.degrees(new_lat), math.degrees(new_lon))

    def start_airport_audio(self):
        """Start audio for airport tower mode"""
        if self.running:
            return
            
        try:
            freq_str = self.freq_entry.get()
            freq = float(freq_str)
            
            # Get selected airport info
            country = self.airport_country_var.get()
            state = self.airport_state_var.get()
            airport = self.airport_var.get()
            service = self.airport_service_var.get()
            
            # Create tower object
            self.airport_tower = Tower(
                name=airport,
                lat=float(self.lat_entry.get()),
                lon=float(self.lon_entry.get()),
                freq=freq
            )
            
            # Start the SDR
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
            self.police_audio_player.start(freq)
            self.running = True
            
            # Start processing thread
            threading.Thread(target=self.read_airport_audio, daemon=True).start()
            
            # Update UI
            self.start_audio_btn.config(state=tk.DISABLED)
            self.stop_audio_btn.config(state=tk.NORMAL)
            self.show_status(f"Listening to {airport} {service} on {freq} MHz")
            
            # Update the map with tower location
            self.update_airport_map()
            
        except Exception as e:
            self.show_status(f"Error: {str(e)}", 5000)
            messagebox.showerror("Error", f"Failed to start: {str(e)}")

    def read_airport_audio(self):
        """Read and process airport tower audio"""
        try:
            chunk_size = 1024 * 4
            
            while self.running and self.sdr_process:
                raw_samples = self.sdr_process.stdout.read(chunk_size)
                if not raw_samples:
                    break
                
                # Play the audio
                self.police_audio_player.play(raw_samples)
                
                # Process for aircraft detection
                self.process_airport_audio(raw_samples)
                        
        except Exception as e:
            self.show_status(f"Read error: {e}", 5000)
        finally:
            if self.running:
                self.root.after(0, self.stop_airport_audio)

    def stop_airport_audio(self):
        """Stop airport tower audio and cleanup"""
        if not self.running:
            return
        
        try:
            # Stop audio
            self.police_audio_player.stop()
            
            # Terminate SDR process
            if self.sdr_process:
                os.killpg(os.getpgid(self.sdr_process.pid), signal.SIGTERM)
                self.sdr_process.wait(timeout=1)
                self.sdr_process = None
        
        except Exception as e:
            self.show_status(f"Error stopping: {str(e)}", 5000)
            return
        
        self.running = False
        self.start_audio_btn.config(state=tk.NORMAL)
        self.stop_audio_btn.config(state=tk.DISABLED)
        self.show_status("Airport audio stopped")



if __name__ == "__main__":
    root = tk.Tk()
    app = SDRApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()