import subprocess
import signal
import sys

class SDRController:
    def __init__(self, freq=98.5):
        self.freq = freq  # in MHz
        self.rtl_process = None
        self.sox_process = None

    def start(self):
        """Start SDR reception and audio playback"""
        try:
            # Command to capture FM radio
            rtl_cmd = f"rtl_fm -f {self.freq}e6 -M fm -s 200k -r 44.1k -A fast"
            
            # Command to play audio
            play_cmd = "play -r 44.1k -t raw -e s -b 16 -c 1 -V1 -"
            
            # Start processes
            self.rtl_process = subprocess.Popen(
                rtl_cmd.split(), 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            self.sox_process = subprocess.Popen(
                play_cmd.split(),
                stdin=self.rtl_process.stdout,
                stderr=subprocess.PIPE
            )
            
            print(f"Listening to {self.freq} MHz FM. Press Ctrl+C to stop.")
            self.sox_process.wait()
            
        except KeyboardInterrupt:
            self.stop()
            
    def stop(self):
        """Cleanup processes"""
        if self.rtl_process:
            self.rtl_process.terminate()
        if self.sox_process:
            self.sox_process.terminate()
        print("\nStopped.")

if __name__ == "__main__":
    controller = SDRController(freq=98.5)  # Change frequency here
    controller.start()