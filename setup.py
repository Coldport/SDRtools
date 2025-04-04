import os
import sys
import subprocess
import platform
import argparse
from setuptools import setup, find_packages

def install_dependencies():
    """Install all required dependencies for the SDR tools application"""
    print("Installing Python dependencies...")
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
        is_raspberry_pi = os.path.exists("/proc/device-tree/model") and "raspberry pi" in open("/proc/device-tree/model").read().lower()
        
        if is_raspberry_pi:
            print("Detected Raspberry Pi, installing dependencies...")
            # Update package lists
            subprocess.run(["sudo", "apt-get", "update"], check=True)
            
            # Install system dependencies for Raspberry Pi
            subprocess.run([
                "sudo", "apt-get", "install", "-y",
                "python3-pyaudio",
                "librtlsdr-dev",
                "rtl-sdr",
                "portaudio19-dev",
                "python3-pip",
                "python3-tk",
                "python3-pil",
                "python3-pil.imagetk"
            ], check=True)
            
            # Install RTL-SDR tools
            subprocess.run([
                "sudo", "apt-get", "install", "-y",
                "rtl-sdr",
                "rtl-fm",
                "rtl-tcp",
                "rtl-eeprom",
                "rtl_test",
                "rtl_power"
            ], check=True)
            
            # Set up udev rules for RTL-SDR
            udev_rules = """# RTL-SDR
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", GROUP="plugdev", MODE="0666"
"""
            with open("/tmp/rtl-sdr.rules", "w") as f:
                f.write(udev_rules)
                
            subprocess.run(["sudo", "mv", "/tmp/rtl-sdr.rules", "/etc/udev/rules.d/"], check=True)
            subprocess.run(["sudo", "udevadm", "control", "--reload-rules"], check=True)
            subprocess.run(["sudo", "udevadm", "trigger"], check=True)
            
            print("Raspberry Pi dependencies installed successfully!")
        else:
            # Check if we're on a Debian-based system
            if os.path.exists("/etc/debian_version"):
                subprocess.run(["sudo", "apt-get", "update"], check=True)
                subprocess.run(["sudo", "apt-get", "install", "-y", "python3-pyaudio", "librtlsdr-dev", "rtl-sdr"], check=True)
            # Add other Linux distributions as needed
    
    elif system == "Windows":
        print("Please install the following manually on Windows:")
        print("1. RTL-SDR drivers from https://www.rtl-sdr.com/")
        print("2. PortAudio from http://portaudio.com/")
        print("3. Visual C++ Redistributable from Microsoft")

def main():
    """Main entry point for the setup script"""
    parser = argparse.ArgumentParser(description="SDR Tools Setup")
    parser.add_argument("--install", action="store_true", help="Install dependencies")
    parser.add_argument("--run", action="store_true", help="Run the SDR Tools application")
    args = parser.parse_args()
    
    if args.install:
        install_dependencies()
    elif args.run:
        # Run the application
        subprocess.run([sys.executable, "code/SDR_tools.py"], check=True)
    else:
        # If no command is provided, show help
        parser.print_help()

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
    entry_points={
        'console_scripts': [
            'sdr-tools=setup:main',
        ],
    },
)

if __name__ == "__main__":
    main() 