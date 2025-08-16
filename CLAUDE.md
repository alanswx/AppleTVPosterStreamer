# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
```bash
# Start the slideshow server
python app.py

# Run with custom configuration
FLASK_PORT=9000 DEBUG=False python app.py

# Enable detailed pyatv logging
DEBUG=True python app.py
```

### Dependencies
```bash
# Install all dependencies
pip install -r requirements.txt

# Key dependencies for understanding:
# - pyatv: AirPlay device communication
# - Flask + Flask-SocketIO: Web server and real-time updates
# - Pillow: Image processing and optimization
# - cryptography: Device credential encryption
# - aiosqlite: Async SQLite operations
```

## Architecture Overview

This is an **asyncio-based Flask application** that streams images to multiple AirPlay devices simultaneously. The core challenge solved is **concurrent device management** while maintaining **synchronized slideshow control**.

### Threading Model
- **Main Thread**: Flask web server and HTTP requests
- **AsyncIO Thread**: All device communication, database operations, and slideshow logic
- **Bridge Pattern**: `run_coroutine()` function bridges synchronous Flask routes to async operations

### Component Interaction Flow
1. **Web Interface** (templates/index.html + static/js/app.js) sends HTTP requests
2. **Flask Routes** (app.py) receive requests and call `run_coroutine()` 
3. **AsyncIO Thread** executes device operations through manager classes
4. **WebSocket Events** provide real-time status updates back to UI

### Core Manager Classes

#### DeviceManager (device_manager.py)
- **Device Discovery**: Uses `pyatv.scan()` for network discovery
- **Connection Management**: Handles concurrent connections with retry logic
- **Authentication**: Manages PIN-based pairing and credential storage
- **Health Monitoring**: Background reconnection for failed devices

#### AirPlayStreamManager (airplay_manager.py) 
- **HTTP Image Server**: Runs embedded server to serve optimized images
- **Concurrent Streaming**: Uses `asyncio.gather()` for simultaneous device streaming
- **Image Optimization**: Auto-resizes to 4K and compresses to 85% JPEG quality
- **URL Generation**: Creates temporary URLs for each image per device

#### SlideshowController (slideshow_controller.py)
- **Round-Robin Distribution**: Core algorithm that distributes images across devices
- **Slideshow State Machine**: Manages start/stop/pause with proper cleanup
- **Real-time Callbacks**: Notifies UI of status changes via WebSocket
- **Session Persistence**: Saves/restores slideshow configuration

#### DatabaseManager (database.py)
- **Encrypted Credentials**: Uses Fernet encryption for AirPlay device credentials
- **Device Registry**: Persistent storage of discovered devices and connection state
- **Session Management**: Stores slideshow configurations for resume functionality

### Critical Configuration Points

#### Port Management
- **Flask Server**: Port 8080 (avoids conflict with AirPlay port 5000)
- **Image Server**: Dynamic port allocation for serving images to devices
- **AirPlay Protocol**: Uses standard AirPlay ports (7000, 7001) for device communication

#### Image Distribution Algorithm
```python
# For N devices and M images:
# Round 1: devices[0..N-1] get images[0..N-1]  
# Round 2: devices[0..N-1] get images[N..2N-1]
# Continues cycling through images[0..M-1]
```

#### AsyncIO Integration Patterns
- **Device Operations**: All pyatv calls must run in async context
- **Database Operations**: Uses aiosqlite for non-blocking database access
- **Error Handling**: Graceful degradation when devices become unavailable
- **Callback System**: Real-time UI updates via registered callback functions

## Development Guidelines

### Adding New Device Types
Extend `DeviceManager.scan_for_devices()` and `DeviceManager.connect_to_device()` to support additional protocols beyond AirPlay.

### Image Format Support
Modify `AirPlayStreamManager._prepare_image()` to handle new formats. All images are normalized to JPEG for AirPlay compatibility.

### Web Interface Extensions  
The JavaScript frontend uses WebSocket for real-time updates. Add new socket event handlers in `static/js/app.js` and corresponding Flask-SocketIO events in `app.py`.

### Authentication Methods
Device credentials are stored encrypted in SQLite. The `DatabaseManager._encrypt_credentials()` method handles secure storage of sensitive pairing data.

## Configuration

Environment variables override defaults in `config.py`:
- `FLASK_HOST/FLASK_PORT`: Server binding
- `DEFAULT_DISPLAY_TIME`: Image display duration (seconds)
- `MAX_DISPLAYS`: Maximum concurrent devices (default: 16)
- `DEFAULT_IMAGES_DIR`: Default image directory path
- `DEBUG`: Enables detailed logging from pyatv library