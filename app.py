from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import asyncio
import threading
import logging
import os
from datetime import datetime
from pathlib import Path

from config import config
from database import DatabaseManager
from device_manager import DeviceManager
from airplay_manager import AirPlayStreamManager
from slideshow_controller import SlideshowController

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*")

# Global managers
db_manager = None
device_manager = None
airplay_manager = None
slideshow_controller = None
event_loop = None
loop_thread = None

def run_async_loop():
    """Run asyncio event loop in separate thread"""
    global event_loop
    event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(event_loop)
    event_loop.run_forever()

def run_coroutine(coro):
    """Run coroutine in the async event loop"""
    if event_loop:
        future = asyncio.run_coroutine_threadsafe(coro, event_loop)
        return future.result(timeout=30)
    return None

async def init_managers():
    """Initialize all managers"""
    global db_manager, device_manager, airplay_manager, slideshow_controller
    
    # Initialize database
    db_manager = DatabaseManager()
    await db_manager.init_database()
    
    # Initialize device manager
    device_manager = DeviceManager(db_manager)
    
    # Initialize AirPlay manager
    airplay_manager = AirPlayStreamManager(device_manager)
    
    # Initialize slideshow controller
    slideshow_controller = SlideshowController(device_manager, airplay_manager, db_manager)
    
    # Register callbacks for real-time updates
    slideshow_controller.register_status_callback(status_update_callback)
    slideshow_controller.register_error_callback(error_callback)
    slideshow_controller.register_video_progress_callback(video_progress_callback)
    
    # Register authentication callback
    def auth_callback(device_id, error_msg):
        socketio.emit('authentication_required', {
            'device_id': device_id,
            'message': error_msg
        })
    
    for device_id in await db_manager.get_all_devices():
        device_manager.register_authentication_callback(device_id['device_id'], auth_callback)

async def status_update_callback(status):
    """Callback for slideshow status updates"""
    # Convert datetime objects to ISO format for JSON serialization
    def serialize_datetime(obj):
        if isinstance(obj, dict):
            return {k: serialize_datetime(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [serialize_datetime(item) for item in obj]
        elif hasattr(obj, 'isoformat'):  # datetime objects
            return obj.isoformat()
        else:
            return obj
    
    # For state-changing events, include full status so UI can update button states
    if status.get('type') in ['slideshow_started', 'slideshow_stopped', 'configuration_updated']:
        full_status = slideshow_controller.get_status()
        full_status['type'] = status.get('type')  # Preserve the event type
        serialized_status = serialize_datetime(full_status)
    else:
        serialized_status = serialize_datetime(status)
    
    socketio.emit('slideshow_status', serialized_status)

async def error_callback(error_info):
    """Callback for error notifications"""
    socketio.emit('error', error_info)

async def video_progress_callback(progress_data):
    """Callback for video creation progress updates"""
    socketio.emit('video_progress', progress_data)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/test')
def test():
    return send_from_directory('.', 'test.html')

@app.route('/debug')
def debug():
    return send_from_directory('.', 'debug.html')

@app.route('/api/scan-devices', methods=['POST'])
def scan_devices():
    """Scan for AirPlay devices"""
    try:
        if device_manager is None:
            return jsonify({'success': False, 'error': 'Device manager not initialized'})
        devices = run_coroutine(device_manager.scan_for_devices())
        return jsonify({'success': True, 'devices': devices})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/devices', methods=['GET'])
def get_devices():
    """Get all known devices"""
    try:
        devices = run_coroutine(db_manager.get_all_devices())
        return jsonify({'success': True, 'devices': devices})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/connect-device', methods=['POST'])
def connect_device():
    """Connect to a device"""
    data = request.get_json()
    device_id = data.get('device_id')
    
    if not device_id:
        return jsonify({'success': False, 'error': 'Device ID required'})
    
    try:
        success = run_coroutine(device_manager.connect_to_device(device_id))
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/start-pairing', methods=['POST'])
def start_pairing():
    """Start AirPlay pairing process"""
    data = request.get_json()
    device_id = data.get('device_id')
    
    if not device_id:
        return jsonify({'success': False, 'error': 'Device ID required'})
    
    try:
        result = run_coroutine(device_manager.start_pairing(device_id))
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/complete-pairing', methods=['POST'])
def complete_pairing():
    """Complete AirPlay pairing with PIN"""
    data = request.get_json()
    device_id = data.get('device_id')
    pin = data.get('pin')
    
    if not device_id or not pin:
        return jsonify({'success': False, 'error': 'Device ID and PIN required'})
    
    try:
        success = run_coroutine(device_manager.complete_pairing(device_id, pin))
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/cancel-pairing', methods=['POST'])
def cancel_pairing():
    """Cancel active pairing process"""
    data = request.get_json()
    device_id = data.get('device_id')
    
    if not device_id:
        return jsonify({'success': False, 'error': 'Device ID required'})
    
    try:
        success = run_coroutine(device_manager.cancel_pairing(device_id))
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/authenticate-device', methods=['POST'])
def authenticate_device():
    """Legacy authenticate device with PIN (deprecated)"""
    data = request.get_json()
    device_id = data.get('device_id')
    pin = data.get('pin')
    
    if not device_id or not pin:
        return jsonify({'success': False, 'error': 'Device ID and PIN required'})
    
    try:
        success = run_coroutine(device_manager.authenticate_device(device_id, pin))
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/disconnect-device', methods=['POST'])
def disconnect_device():
    """Disconnect from a device"""
    data = request.get_json()
    device_id = data.get('device_id')
    
    if not device_id:
        return jsonify({'success': False, 'error': 'Device ID required'})
    
    try:
        run_coroutine(device_manager.disconnect_device(device_id))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/directories')
def get_directories():
    """Get available image directories"""
    try:
        base_dir = Path(config.DEFAULT_IMAGES_DIR)
        directories = []
        
        # Add current directory
        if base_dir.exists():
            directories.append({
                'path': str(base_dir),
                'name': base_dir.name,
                'image_count': len(list(base_dir.glob('*.jpg'))) + len(list(base_dir.glob('*.jpeg'))) + len(list(base_dir.glob('*.png')))
            })
        
        # Add parent directory contents for browsing
        parent_dir = Path.cwd()
        for item in parent_dir.iterdir():
            if item.is_dir() and item.name != '.git':
                image_count = 0
                try:
                    for ext in config.SUPPORTED_IMAGE_FORMATS:
                        image_count += len(list(item.glob(f'*{ext}')))
                except:
                    pass
                
                if image_count > 0:
                    directories.append({
                        'path': str(item),
                        'name': item.name,
                        'image_count': image_count
                    })
        
        return jsonify({'success': True, 'directories': directories})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/configure-slideshow', methods=['POST'])
def configure_slideshow():
    """Configure slideshow parameters"""
    data = request.get_json()
    images_directory = data.get('images_directory')
    devices = data.get('devices', [])
    display_time = data.get('display_time', config.DEFAULT_DISPLAY_TIME)
    video_mode = data.get('video_mode', False)
    transition_duration = data.get('transition_duration', 1.0)
    
    if not images_directory:
        return jsonify({'success': False, 'error': 'Images directory required'})
    
    if not devices:
        return jsonify({'success': False, 'error': 'At least one device required'})
    
    try:
        success = run_coroutine(slideshow_controller.configure_slideshow(
            images_directory, devices, display_time, video_mode, transition_duration
        ))
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/start-slideshow', methods=['POST'])
def start_slideshow():
    """Start the slideshow"""
    try:
        success = run_coroutine(slideshow_controller.start_slideshow())
        if success:
            return jsonify({'success': True})
        else:
            # Check why it failed
            if slideshow_controller.is_running:
                return jsonify({'success': False, 'error': 'Slideshow is already running'})
            elif not slideshow_controller.current_images or not slideshow_controller.active_devices:
                return jsonify({'success': False, 'error': 'Slideshow not configured. Set images directory and devices first.'})
            else:
                return jsonify({'success': False, 'error': 'Failed to start slideshow'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/stop-slideshow', methods=['POST'])
def stop_slideshow():
    """Stop the slideshow"""
    try:
        success = run_coroutine(slideshow_controller.stop_slideshow())
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/slideshow-status')
def get_slideshow_status():
    """Get current slideshow status"""
    try:
        status = slideshow_controller.get_status()
        return jsonify({'success': True, 'status': status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/next-images', methods=['POST'])
def next_images():
    """Advance to next set of images"""
    try:
        success = run_coroutine(slideshow_controller.next_images())
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/previous-images', methods=['POST'])
def previous_images():
    """Go back to previous set of images"""
    try:
        success = run_coroutine(slideshow_controller.previous_images())
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/update-display-time', methods=['POST'])
def update_display_time():
    """Update display time"""
    data = request.get_json()
    display_time = data.get('display_time')
    
    if not display_time or display_time <= 0:
        return jsonify({'success': False, 'error': 'Valid display time required'})
    
    try:
        success = run_coroutine(slideshow_controller.update_display_time(display_time))
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    emit('connected', {'message': 'Connected to AirPlay Slideshow'})

@app.route('/video/<filename>')
def serve_video(filename):
    """Serve video files for AirPlay streaming"""
    try:
        # Get video path from slideshow controller's video creator
        if hasattr(slideshow_controller, 'video_creator'):
            video_dir = slideshow_controller.video_creator.temp_video_dir
            return send_from_directory(video_dir, filename)
        else:
            return "Video creator not available", 404
    except Exception as e:
        return f"Error serving video: {str(e)}", 500

@socketio.on('request_status')
def handle_status_request():
    """Handle status request from client"""
    try:
        status = slideshow_controller.get_status()
        emit('slideshow_status', {'type': 'full_status', **status})
    except Exception as e:
        emit('error', {'message': f'Error getting status: {str(e)}'})

if __name__ == '__main__':
    # Start async event loop in separate thread
    loop_thread = threading.Thread(target=run_async_loop, daemon=True)
    loop_thread.start()
    
    # Give the async thread time to start
    import time
    time.sleep(0.5)
    
    # Initialize managers
    try:
        run_coroutine(init_managers())
        print("Managers initialized successfully")
    except Exception as e:
        print(f"Failed to initialize managers: {e}")
    
    # Try to load last session
    try:
        run_coroutine(slideshow_controller.load_last_session())
    except:
        pass
    
    print(f"Starting AirPlay Slideshow server on http://{config.FLASK_HOST}:{config.FLASK_PORT}")
    print("Open your web browser and navigate to the above URL to control the slideshow")
    
    # Run Flask app
    socketio.run(
        app, 
        host=config.FLASK_HOST, 
        port=config.FLASK_PORT, 
        debug=config.DEBUG,
        allow_unsafe_werkzeug=True
    )