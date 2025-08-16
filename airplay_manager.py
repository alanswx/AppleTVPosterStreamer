import asyncio
import os
import tempfile
import logging
from typing import List, Dict, Any, Optional
from PIL import Image
import http.server
import socketserver
import threading
from urllib.parse import quote
from pyatv.const import FeatureName, FeatureState, Protocol
from device_manager import DeviceManager
from config import config

class AirPlayStreamManager:
    def __init__(self, device_manager: DeviceManager):
        self.device_manager = device_manager
        self.logger = logging.getLogger(__name__)
        self.web_server = None
        self.web_server_port = None
        self.web_server_thread = None
        self.served_files: Dict[str, str] = {}  # filename -> full_path mapping
        
    async def start_web_server(self):
        """Start a simple HTTP server to serve images to AirPlay devices"""
        if self.web_server is not None:
            return
            
        # Find available port
        import socket
        sock = socket.socket()
        sock.bind(('', 0))
        self.web_server_port = sock.getsockname()[1]
        sock.close()
        
        class ImageHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, served_files=None, **kwargs):
                self.served_files = served_files or {}
                super().__init__(*args, **kwargs)
            
            def do_GET(self):
                # Extract filename from path
                filename = self.path.lstrip('/')
                if filename in self.served_files:
                    file_path = self.served_files[filename]
                    try:
                        with open(file_path, 'rb') as f:
                            self.send_response(200)
                            self.send_header('Content-Type', 'image/jpeg')
                            self.send_header('Content-Length', str(os.path.getsize(file_path)))
                            self.end_headers()
                            self.wfile.write(f.read())
                        return
                    except Exception as e:
                        print(f"Error serving file {file_path}: {e}")
                
                self.send_response(404)
                self.end_headers()
            
            def log_message(self, format, *args):
                pass  # Suppress log messages
        
        def create_handler(*args, **kwargs):
            return ImageHandler(*args, served_files=self.served_files, **kwargs)
        
        def start_server():
            with socketserver.TCPServer(("", self.web_server_port), create_handler) as httpd:
                self.web_server = httpd
                self.logger.info(f"Started image server on port {self.web_server_port}")
                httpd.serve_forever()
        
        self.web_server_thread = threading.Thread(target=start_server, daemon=True)
        self.web_server_thread.start()
        
        # Give the server a moment to start
        await asyncio.sleep(0.5)
    
    def stop_web_server(self):
        """Stop the HTTP server"""
        if self.web_server:
            self.web_server.shutdown()
            self.web_server = None
            self.web_server_port = None
        if self.web_server_thread:
            self.web_server_thread.join(timeout=1)
            self.web_server_thread = None
    
    def _prepare_image(self, image_path: str) -> Optional[str]:
        """Prepare image for streaming - resize if needed and return optimized path"""
        try:
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize if image is too large
                if img.size[0] > config.MAX_IMAGE_SIZE[0] or img.size[1] > config.MAX_IMAGE_SIZE[1]:
                    img.thumbnail(config.MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
                    
                    # Save optimized version to temp file
                    temp_fd, temp_path = tempfile.mkstemp(suffix='.jpg', prefix='airplay_')
                    os.close(temp_fd)
                    
                    img.save(temp_path, 'JPEG', quality=config.IMAGE_QUALITY, optimize=True)
                    return temp_path
                else:
                    # Image is fine as-is
                    return image_path
                    
        except Exception as e:
            self.logger.error(f"Error preparing image {image_path}: {e}")
            return None
    
    def _get_image_url(self, image_path: str) -> Optional[str]:
        """Get URL for serving image through local web server"""
        prepared_path = self._prepare_image(image_path)
        if not prepared_path:
            return None
        
        # Generate unique filename for serving
        filename = f"image_{len(self.served_files)}.jpg"
        self.served_files[filename] = prepared_path
        
        # Get local IP address
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        
        url = f"http://{local_ip}:{self.web_server_port}/{filename}"
        return url
    
    async def check_airplay_pairing_required(self, device_id: str) -> Dict[str, Any]:
        """Check if device requires AirPlay pairing for streaming"""
        if not self.device_manager.is_device_connected(device_id):
            return {"error": "Device not connected"}
        
        connection = self.device_manager.get_device_connection(device_id)
        if not connection:
            return {"error": "No connection found"}
        
        try:
            pairing_info = {
                "device_id": device_id,
                "requires_pairing": False,
                "has_airplay_credentials": False,
                "pairing_suggestions": []
            }
            
            # Check if device has AirPlay service configured with credentials
            device_config = self.device_manager.get_device_config(device_id)
            if device_config:
                airplay_service = device_config.get_service(Protocol.AirPlay)
                if airplay_service and airplay_service.credentials:
                    pairing_info["has_airplay_credentials"] = True
                else:
                    pairing_info["requires_pairing"] = True
                    pairing_info["pairing_suggestions"].append(
                        f"Use: atvremote --id {device_id} --airplay-credentials <credentials> pair"
                    )
            
            # Check feature states that might indicate pairing issues
            diagnosis = await self.diagnose_device_capabilities(device_id)
            play_url_state = diagnosis.get("stream_features", {}).get("PlayUrl", "Unknown")
            
            if play_url_state == "Unavailable":
                pairing_info["requires_pairing"] = True
                pairing_info["pairing_suggestions"].extend([
                    "PlayUrl feature is 'Unavailable' which often indicates authentication issues",
                    "Try pairing the device for AirPlay streaming",
                    "Ensure the device supports AirPlay image streaming"
                ])
            
            return pairing_info
            
        except Exception as e:
            return {"error": f"Failed to check pairing requirements: {e}"}

    async def diagnose_device_capabilities(self, device_id: str) -> Dict[str, Any]:
        """Diagnose device capabilities for streaming"""
        if not self.device_manager.is_device_connected(device_id):
            return {"error": "Device not connected"}
        
        connection = self.device_manager.get_device_connection(device_id)
        if not connection:
            return {"error": "No connection found"}
        
        try:
            diagnosis = {
                "device_id": device_id,
                "available_interfaces": [],
                "stream_features": {},
                "all_features": {}
            }
            
            # Check available interfaces
            interfaces = ["stream", "remote_control", "metadata", "power", "apps"]
            for interface in interfaces:
                if hasattr(connection, interface):
                    diagnosis["available_interfaces"].append(interface)
            
            # Check stream-related features
            stream_features = [FeatureName.PlayUrl, FeatureName.StreamFile]
            for feature in stream_features:
                try:
                    feature_info = connection.features.get_feature(feature)
                    diagnosis["stream_features"][feature.name] = feature_info.state.name
                except:
                    diagnosis["stream_features"][feature.name] = "Unknown"
            
            # Get all available features
            try:
                all_features = connection.features.all_features()
                diagnosis["all_features"] = {
                    name.name: feature.state.name 
                    for name, feature in all_features.items()
                    if feature.state == FeatureState.Available
                }
            except Exception as e:
                diagnosis["all_features"] = {"error": str(e)}
            
            return diagnosis
            
        except Exception as e:
            return {"error": f"Failed to diagnose device: {e}"}
    
    async def stream_image_to_device(self, device_id: str, image_path: str) -> bool:
        """Stream a single image to a specific device"""
        if not self.device_manager.is_device_connected(device_id):
            self.logger.error(f"Device {device_id} is not connected")
            return False
        
        connection = self.device_manager.get_device_connection(device_id)
        if not connection:
            self.logger.error(f"No connection found for device {device_id}")
            return False
        
        try:
            # First run diagnostics to understand device capabilities
            diagnosis = await self.diagnose_device_capabilities(device_id)
            self.logger.info(f"Device {device_id} capabilities: {diagnosis}")
            
            # Check AirPlay pairing requirements
            pairing_info = await self.check_airplay_pairing_required(device_id)
            self.logger.info(f"Device {device_id} pairing info: {pairing_info}")
            
            # Check AirPlay streaming support
            play_url_state = diagnosis.get("stream_features", {}).get("PlayUrl", "Unknown")
            
            if play_url_state == "Unsupported":
                self.logger.error(f"Device {device_id} does not support PlayUrl feature for image streaming")
                self.logger.error("According to pyatv documentation, PlayUrl via AirPlay is the only method for streaming images")
                self.logger.error("Alternative: Consider using stream_file() for audio content or check if device requires pairing")
                return False
            elif play_url_state == "Unavailable":
                self.logger.warning(f"Device {device_id} PlayUrl feature is currently unavailable")
                self.logger.warning("This may indicate the device requires AirPlay pairing/authentication")
                self.logger.warning("Try pairing with the device first using atvremote pair command")
                
                # Still attempt to stream in case the status is incorrectly reported
                self.logger.info("Attempting to stream despite 'Unavailable' status...")
            elif play_url_state != "Available":
                self.logger.warning(f"Device {device_id} PlayUrl feature state: {play_url_state}")
            
            # Ensure web server is running
            await self.start_web_server()
            
            # Get URL for the image
            image_url = self._get_image_url(image_path)
            if not image_url:
                self.logger.error(f"Failed to prepare image {image_path}")
                return False
            
            self.logger.info(f"Streaming {image_path} to device {device_id} via {image_url}")
            
            # According to pyatv documentation, play_url is the ONLY method for streaming images via AirPlay
            # There is no alternative method when play_url is not supported
            await connection.stream.play_url(image_url)
            self.logger.info(f"Successfully started streaming to device {device_id}")
            return True
            
        except Exception as e:
            # Check if this is a not supported error
            error_str = str(e).lower()
            if "not supported" in error_str or "unsupported" in error_str:
                self.logger.error(f"Device {device_id} does not support image streaming via AirPlay: {e}")
                self.logger.error("According to pyatv documentation:")
                self.logger.error("- play_url() is for images/video via AirPlay protocol")
                self.logger.error("- stream_file() is for audio only via RAOP protocol")
                self.logger.error("- No alternative exists for image streaming when AirPlay is unsupported")
                self.logger.error("Suggestions:")
                self.logger.error("1. Verify device supports AirPlay image streaming")
                self.logger.error("2. Check if device requires pairing: atvremote --id <device_id> pair")
                self.logger.error("3. Ensure device credentials are properly configured")
                
                # Log available features for debugging
                try:
                    available_features = connection.features.all_features()
                    feature_names = [name.name for name, feature in available_features.items() if feature.state == FeatureState.Available]
                    self.logger.info(f"Device {device_id} available features: {feature_names}")
                except:
                    pass
                    
            else:
                self.logger.error(f"Failed to stream image to device {device_id}: {e}")
            return False
    
    async def stream_images_to_devices(self, device_image_mapping: Dict[str, str]) -> Dict[str, bool]:
        """Stream different images to multiple devices concurrently"""
        if not device_image_mapping:
            return {}
        
        # Ensure web server is running
        await self.start_web_server()
        
        # Create concurrent streaming tasks
        tasks = []
        device_ids = []
        
        for device_id, image_path in device_image_mapping.items():
            if self.device_manager.is_device_connected(device_id):
                task = asyncio.create_task(
                    self.stream_image_to_device(device_id, image_path)
                )
                tasks.append(task)
                device_ids.append(device_id)
            else:
                self.logger.warning(f"Skipping disconnected device {device_id}")
        
        if not tasks:
            self.logger.warning("No connected devices to stream to")
            return {}
        
        # Wait for all streaming tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Compile results
        streaming_results = {}
        for i, device_id in enumerate(device_ids):
            if isinstance(results[i], Exception):
                self.logger.error(f"Exception streaming to {device_id}: {results[i]}")
                streaming_results[device_id] = False
            else:
                streaming_results[device_id] = results[i]
        
        return streaming_results
    
    async def stream_video_to_device(self, device_id: str, video_path: str) -> bool:
        """Stream a video file to a specific device"""
        if not self.device_manager.is_device_connected(device_id):
            self.logger.error(f"Device {device_id} is not connected")
            return False
        
        connection = self.device_manager.get_device_connection(device_id)
        if not connection:
            self.logger.error(f"No connection found for device {device_id}")
            return False
        
        try:
            # Ensure web server is running
            await self.start_web_server()
            
            # Serve the video file
            filename = f"video_{len(self.served_files)}.mp4"
            self.served_files[filename] = video_path
            
            # Get local IP address
            import socket
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            
            video_url = f"http://{local_ip}:{self.web_server_port}/{filename}"
            
            self.logger.info(f"Streaming video {video_path} to device {device_id} via {video_url}")
            
            # Stream video using play_url (videos have better compatibility than images)
            await connection.stream.play_url(video_url)
            self.logger.info(f"Successfully started video streaming to device {device_id}")
            return True
            
        except Exception as e:
            error_str = str(e).lower()
            if "not supported" in error_str or "unsupported" in error_str:
                self.logger.error(f"Device {device_id} does not support video streaming: {e}")
            else:
                self.logger.error(f"Failed to stream video to device {device_id}: {e}")
            return False
    
    async def stream_videos_to_devices(self, device_video_mapping: Dict[str, str]) -> Dict[str, bool]:
        """Stream different videos to multiple devices concurrently"""
        if not device_video_mapping:
            return {}
        
        # Ensure web server is running
        await self.start_web_server()
        
        # Create concurrent streaming tasks
        tasks = []
        device_ids = []
        
        for device_id, video_path in device_video_mapping.items():
            if self.device_manager.is_device_connected(device_id):
                task = asyncio.create_task(
                    self.stream_video_to_device(device_id, video_path)
                )
                tasks.append(task)
                device_ids.append(device_id)
            else:
                self.logger.warning(f"Skipping disconnected device {device_id}")
        
        if not tasks:
            self.logger.warning("No connected devices to stream videos to")
            return {}
        
        # Wait for all streaming tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Compile results
        streaming_results = {}
        for i, device_id in enumerate(device_ids):
            if isinstance(results[i], Exception):
                self.logger.error(f"Exception streaming video to {device_id}: {results[i]}")
                streaming_results[device_id] = False
            else:
                streaming_results[device_id] = results[i]
        
        return streaming_results
    
    async def stop_playback_on_device(self, device_id: str) -> bool:
        """Stop playback on a specific device"""
        if not self.device_manager.is_device_connected(device_id):
            return False
        
        connection = self.device_manager.get_device_connection(device_id)
        if not connection:
            return False
        
        try:
            await connection.stream.stop()
            self.logger.info(f"Stopped playback on device {device_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to stop playback on device {device_id}: {e}")
            return False
    
    async def stop_playback_on_all_devices(self) -> Dict[str, bool]:
        """Stop playback on all connected devices"""
        connected_devices = self.device_manager.get_connected_devices()
        
        if not connected_devices:
            return {}
        
        # Create concurrent stop tasks
        tasks = [
            asyncio.create_task(self.stop_playback_on_device(device_id))
            for device_id in connected_devices
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        stop_results = {}
        for i, device_id in enumerate(connected_devices):
            if isinstance(results[i], Exception):
                self.logger.error(f"Exception stopping playback on {device_id}: {results[i]}")
                stop_results[device_id] = False
            else:
                stop_results[device_id] = results[i]
        
        return stop_results
    
    async def get_playback_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get current playback status from a device"""
        if not self.device_manager.is_device_connected(device_id):
            return None
        
        connection = self.device_manager.get_device_connection(device_id)
        if not connection:
            return None
        
        try:
            # Note: Actual implementation depends on pyatv capabilities
            # This is a placeholder for future enhancement
            return {
                'device_id': device_id,
                'is_playing': True,  # Would get actual status
                'position': 0,
                'duration': 0
            }
        except Exception as e:
            self.logger.error(f"Failed to get playback status from device {device_id}: {e}")
            return None
    
    def cleanup(self):
        """Clean up resources"""
        self.stop_web_server()
        
        # Clean up temporary files
        for filename, file_path in self.served_files.items():
            if file_path.startswith(tempfile.gettempdir()):
                try:
                    os.unlink(file_path)
                except:
                    pass
        
        self.served_files.clear()