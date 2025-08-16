# AirPlay Slideshow Controller

A Python-based web application that streams images to multiple AirPlay devices simultaneously, creating synchronized slideshows across multiple displays.

## Features

- **Multi-Device Streaming**: Send different images to up to 16 AirPlay devices concurrently
- **Web Interface**: Control everything through a modern web browser interface
- **Device Discovery**: Automatic scanning and discovery of AirPlay devices on the network
- **Authentication Management**: Handle PIN authentication and store credentials securely
- **Image Distribution**: Round-robin algorithm distributes images across displays
- **Real-time Control**: Start, stop, and navigate through slideshow remotely
- **Statistics Tracking**: Monitor slideshow performance and device status
- **Configurable Timing**: Adjust display intervals during slideshow

## Supported Devices

- Samsung Smart TVs with AirPlay 2 support (Q8F series and newer)
- Apple TV (all generations)
- AirPlay-compatible smart displays
- HomePod, AirPort Express (audio streaming)

## Installation

1. **Clone or create the project directory:**
   ```bash
   cd airplay-slideshow
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Prepare your images:**
   - Place JPEG images in the `images/` directory or any directory you choose
   - Supported formats: .jpg, .jpeg, .png, .gif
   - Images will be automatically optimized for streaming

## Usage

1. **Start the application:**
   ```bash
   python app.py
   ```

2. **Open web interface:**
   - Navigate to `http://localhost:8080` in your web browser
   - Or use the IP address shown in the terminal for remote access

3. **Set up devices:**
   - Click "Scan" to discover AirPlay devices on your network
   - Connect to devices (enter PIN if prompted)
   - Select which devices to use for slideshow

4. **Configure slideshow:**
   - Choose an images directory
   - Select connected devices
   - Set display time (seconds per image)
   - Click "Configure Slideshow"

5. **Control slideshow:**
   - Click "Start" to begin slideshow
   - Use navigation buttons to manually advance/reverse
   - Adjust timing while running
   - Monitor statistics and logs

## How It Works

### Image Distribution Algorithm

For 3 displays and 6 images (1.jpg, 2.jpg, 3.jpg, 4.jpg, 5.jpg, 6.jpg):

- **Round 1**: Display 1 → 1.jpg, Display 2 → 2.jpg, Display 3 → 3.jpg
- **Round 2**: Display 1 → 4.jpg, Display 2 → 5.jpg, Display 3 → 6.jpg  
- **Round 3**: Display 1 → 1.jpg, Display 2 → 2.jpg, Display 3 → 3.jpg (loops)

### Architecture

- **Flask Web Server**: Provides REST API and web interface
- **WebSocket**: Real-time communication for status updates
- **AsyncIO**: Concurrent device management and streaming
- **SQLite Database**: Encrypted storage of device credentials
- **HTTP Image Server**: Serves optimized images to AirPlay devices

## Configuration

### Environment Variables

- `FLASK_HOST`: Server host (default: 0.0.0.0)
- `FLASK_PORT`: Server port (default: 8080)
- `DEFAULT_DISPLAY_TIME`: Default image display time in seconds (default: 5)
- `MAX_DISPLAYS`: Maximum number of displays (default: 16)
- `DEFAULT_IMAGES_DIR`: Default images directory (default: ./images)

### Image Settings

- **Max Resolution**: 4K (3840x2160) - images auto-resized if larger
- **Format**: Optimized JPEG with 85% quality
- **Supported Input**: .jpg, .jpeg, .png, .gif

## Troubleshooting

### Device Connection Issues

1. **PIN Authentication**: Some devices require PIN entry on first connection
2. **Network Discovery**: Ensure devices are on same network
3. **Firewall**: Check that port 8080 and dynamic ports aren't blocked
4. **AirPlay Support**: Verify device supports AirPlay 2

### Common Problems

- **Port 5000 Conflict**: App uses port 8080 to avoid AirPlay receiver conflicts
- **Authentication Timeout**: Re-scan devices if authentication fails
- **Image Loading**: Check file permissions and supported formats
- **Performance**: Reduce image resolution for better streaming performance

### Logs and Debugging

- Check web interface activity log for real-time information
- Enable debug mode by setting `DEBUG=True` in environment
- View terminal output for detailed pyatv communication logs

## Technical Details

### Dependencies

- **pyatv**: AirPlay device communication
- **Flask**: Web framework
- **Flask-SocketIO**: WebSocket support
- **Pillow**: Image processing
- **cryptography**: Credential encryption
- **aiosqlite**: Async database operations

### Network Requirements

- All devices must be on the same local network
- Multicast DNS (mDNS) support for device discovery
- Dynamic port allocation for image serving

### Security

- Device credentials encrypted with Fernet (AES 128)
- Encryption key stored locally with restricted permissions
- No external network access required

## Development

### Project Structure

```
airplay-slideshow/
├── app.py                 # Flask application
├── config.py             # Configuration settings
├── database.py           # Database management
├── device_manager.py     # AirPlay device handling
├── airplay_manager.py    # Image streaming
├── slideshow_controller.py # Slideshow logic
├── static/
│   └── js/app.js         # Frontend JavaScript
├── templates/
│   └── index.html        # Web interface
└── images/               # Default images directory
```

### Adding Features

The modular architecture makes it easy to extend:

- **New device types**: Extend `device_manager.py`
- **Additional image formats**: Update `airplay_manager.py`
- **UI enhancements**: Modify `templates/index.html` and `static/js/app.js`
- **Streaming protocols**: Extend `config.py` and add protocol handlers

## License

MIT License - feel free to use and modify for your needs.