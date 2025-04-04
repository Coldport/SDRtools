import os
import sys
import subprocess
import platform
from setuptools import setup, find_packages

def install_dependencies():
    # Install Python dependencies
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    # OS-specific installations
    system = platform.system()
    
    if system == "Darwin":  # macOS
        try:
            # Check if Homebrew is installed
            subprocess.run(["brew", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError:
            print("Installing Homebrew...")
            subprocess.run('/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"', shell=True)
        
        # Install system dependencies
        subprocess.run(["brew", "install", "portaudio", "rtl-sdr"], check=True)
        
    elif system == "Linux":
        # Check if we're on a Raspberry Pi
        if os.path.exists("/proc/device-tree/model") and "raspberry pi" in open("/proc/device-tree/model").read().lower():
            print("Detected Raspberry Pi - installing required dependencies...")
            # Install system dependencies for Raspberry Pi
            subprocess.run(["sudo", "apt-get", "update"], check=True)
            subprocess.run(["sudo", "apt-get", "install", "-y", 
                          "python3-pyaudio",
                          "portaudio19-dev",
                          "python3-pip",
                          "librtlsdr-dev",
                          "rtl-sdr",
                          "build-essential",
                          "python3-dev"], check=True)
            
            # Install PyAudio using pip with specific options for Raspberry Pi
            subprocess.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", 
                          "pyaudio==0.2.11"], check=True)
        else:
            # Regular Linux installation
            if os.path.exists("/etc/debian_version"):
                subprocess.run(["sudo", "apt-get", "update"], check=True)
                subprocess.run(["sudo", "apt-get", "install", "-y", 
                              "python3-pyaudio", 
                              "librtlsdr-dev", 
                              "rtl-sdr"], check=True)
    
    elif system == "Windows":
        print("Please install the following manually on Windows:")
        print("1. RTL-SDR drivers from https://www.rtl-sdr.com/")
        print("2. PortAudio from http://portaudio.com/")
        print("3. Visual C++ Redistributable from Microsoft")

setup(
    name="sdr-tools",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.21.0",
        "Pillow>=9.0.0",
        "ephem>=4.1.3",
        "pyaudio>=0.2.11",
        "requests>=2.26.0"
    ],
    python_requires=">=3.7",
)

if __name__ == "__main__":
    install_dependencies() 