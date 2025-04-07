# SDR Tools Application

A software-defined radio (SDR) application for receiving and decoding various radio signals including NOAA satellites, FM radio, police frequencies, and airport communications.

## Features
- NOAA APT satellite image reception
- GOES LRIT satellite data reception
- FM radio reception
- Police/emergency services frequency scanning
- Airport tower communication monitoring
- Real-time signal visualization

## System Requirements
- Python 3.8 or higher
- RTL-SDR compatible hardware
- 2GB RAM minimum (4GB recommended)
- 500MB disk space

## Installation

### Windows
1. Install Python from [python.org](https://www.python.org/)
2. Install RTL-SDR drivers from [rtl-sdr.com](https://www.rtl-sdr.com/)
3. Open Command Prompt and run:
```
pip install -r requirements.txt
```
4. Run the application:
```
python SDR_tools.py
```

### macOS
1. Install Homebrew if not already installed:
```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
2. Install dependencies:
```
brew install python rtl-sdr
pip install -r requirements.txt
```
3. Run the application:
```
python3 SDR_tools.py
```

### Linux (Ubuntu/Debian)
1. Install dependencies:
```
sudo apt update
sudo apt install python3 python3-pip rtl-sdr
pip install -r requirements.txt
```
2. Run the application:
```
python3 SDR_tools.py
```

## Usage
1. Connect your RTL-SDR device
2. Launch the application
3. Select your desired mode (NOAA, GOES, FM, Police, or Airport)
4. Configure frequency and location settings
5. Start reception

## Dependencies
- Python 3.8+
- RTL-SDR hardware
- Required Python packages (see requirements.txt)

## Troubleshooting
- **No device found**: Ensure RTL-SDR is properly connected and drivers are installed
- **Poor signal quality**: Check antenna connection and positioning
- **Map display issues**: Install ChromeDriver for map rendering

## License
MIT License

## Contributing
Contributions are welcome! Please open an issue or pull request on GitHub.