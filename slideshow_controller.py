import asyncio
import os
import random
import logging
from typing import List, Dict, Optional, Callable, Any
from pathlib import Path
from datetime import datetime
from device_manager import DeviceManager
from airplay_manager import AirPlayStreamManager
from database import DatabaseManager
from video_creator import VideoCreator
from config import config

class SlideshowController:
    def __init__(self, device_manager: DeviceManager, airplay_manager: AirPlayStreamManager, 
                 db_manager: DatabaseManager):
        self.device_manager = device_manager
        self.airplay_manager = airplay_manager
        self.db_manager = db_manager
        self.video_creator = VideoCreator()
        self.logger = logging.getLogger(__name__)
        
        # Set up video creation progress callback
        self.video_creator.set_progress_callback(self._video_progress_callback)
        
        # Video progress callbacks
        self.video_progress_callbacks: List[Callable] = []
        
        # Slideshow state
        self.is_running = False
        self.current_images_directory = None
        self.current_images: List[str] = []
        self.active_devices: List[str] = []
        self.display_time = config.DEFAULT_DISPLAY_TIME
        self.current_image_index = 0
        self.slideshow_task = None
        self.video_mode = False  # New: whether to use video streaming instead of images
        self.transition_duration = 1.0  # New: fade transition duration for videos
        
        # Callbacks for UI updates
        self.status_callbacks: List[Callable] = []
        self.error_callbacks: List[Callable] = []
        
        # Statistics
        self.slideshow_stats = {
            'started_at': None,
            'images_displayed': 0,
            'cycles_completed': 0,
            'errors': 0
        }
    
    def register_status_callback(self, callback: Callable):
        """Register callback for slideshow status updates"""
        self.status_callbacks.append(callback)
    
    def register_error_callback(self, callback: Callable):
        """Register callback for error notifications"""
        self.error_callbacks.append(callback)
        
    def register_video_progress_callback(self, callback: Callable):
        """Register callback for video creation progress updates"""
        self.video_progress_callbacks.append(callback)
    
    async def _notify_status_change(self, status: Dict[str, Any]):
        """Notify all registered callbacks about status changes"""
        for callback in self.status_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(status)
                else:
                    callback(status)
            except Exception as e:
                self.logger.error(f"Error in status callback: {e}")
    
    async def _notify_error(self, error_msg: str, device_id: str = None):
        """Notify all registered callbacks about errors"""
        error_info = {
            'message': error_msg,
            'device_id': device_id,
            'timestamp': datetime.now().isoformat()
        }
        
        for callback in self.error_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(error_info)
                else:
                    callback(error_info)
            except Exception as e:
                self.logger.error(f"Error in error callback: {e}")
                
    async def _video_progress_callback(self, progress_data: Dict[str, Any]):
        """Handle video creation progress updates"""
        for callback in self.video_progress_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(progress_data)
                else:
                    callback(progress_data)
            except Exception as e:
                self.logger.error(f"Error in video progress callback: {e}")
    
    def load_images_from_directory(self, directory_path: str) -> List[str]:
        """Load all supported image files from directory"""
        if not os.path.exists(directory_path):
            self.logger.error(f"Directory does not exist: {directory_path}")
            return []
        
        images = []
        directory = Path(directory_path)
        
        for file_path in directory.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in config.SUPPORTED_IMAGE_FORMATS:
                images.append(str(file_path.absolute()))
        
        # Sort images naturally (1.jpg, 2.jpg, 10.jpg instead of 1.jpg, 10.jpg, 2.jpg)
        images.sort(key=lambda x: Path(x).stem.lower())
        
        self.logger.info(f"Loaded {len(images)} images from {directory_path}")
        return images
    
    def distribute_images_to_devices(self, devices: List[str], images: List[str], 
                                   start_index: int = 0) -> Dict[str, str]:
        """Distribute images to devices using round-robin algorithm"""
        if not devices or not images:
            return {}
        
        distribution = {}
        num_devices = len(devices)
        num_images = len(images)
        
        for i, device_id in enumerate(devices):
            image_index = (start_index + i) % num_images
            distribution[device_id] = images[image_index]
        
        return distribution
    
    async def configure_slideshow(self, images_directory: str, devices: List[str], 
                                display_time: int = None, video_mode: bool = False,
                                transition_duration: float = 1.0) -> bool:
        """Configure slideshow parameters"""
        try:
            # Validate directory
            if not os.path.exists(images_directory):
                await self._notify_error(f"Images directory does not exist: {images_directory}")
                return False
            
            # Load images
            images = self.load_images_from_directory(images_directory)
            if not images:
                await self._notify_error(f"No supported images found in: {images_directory}")
                return False
            
            # Validate devices
            connected_devices = self.device_manager.get_connected_devices()
            valid_devices = [d for d in devices if d in connected_devices]
            
            if not valid_devices:
                await self._notify_error("No valid connected devices specified")
                return False
            
            if len(valid_devices) != len(devices):
                disconnected = set(devices) - set(valid_devices)
                await self._notify_error(f"Some devices are not connected: {list(disconnected)}")
            
            # Update configuration
            self.current_images_directory = images_directory
            self.current_images = images
            self.active_devices = valid_devices
            self.display_time = display_time or config.DEFAULT_DISPLAY_TIME
            self.current_image_index = 0
            self.video_mode = video_mode
            self.transition_duration = transition_duration
            
            # Save session to database
            await self.db_manager.save_slideshow_session(
                session_name=f"Session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                images_directory=images_directory,
                display_time=self.display_time,
                active_devices=self.active_devices
            )
            
            mode_str = "video" if video_mode else "image"
            self.logger.info(f"Configured slideshow: {len(images)} images, {len(valid_devices)} devices, {self.display_time}s intervals, {mode_str} mode")
            
            await self._notify_status_change({
                'type': 'configuration_updated',
                'images_count': len(images),
                'devices_count': len(valid_devices),
                'display_time': self.display_time,
                'directory': images_directory,
                'video_mode': video_mode,
                'transition_duration': transition_duration
            })
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error configuring slideshow: {e}")
            await self._notify_error(f"Configuration error: {str(e)}")
            return False
    
    async def start_slideshow(self) -> bool:
        """Start the slideshow"""
        if self.is_running:
            self.logger.warning("Slideshow is already running")
            return False
        
        if not self.current_images or not self.active_devices:
            await self._notify_error("Slideshow not configured. Set images directory and devices first.")
            return False
        
        self.is_running = True
        self.slideshow_stats = {
            'started_at': datetime.now(),
            'images_displayed': 0,
            'cycles_completed': 0,
            'errors': 0
        }
        
        self.logger.info("Starting slideshow")
        
        # Start slideshow task
        self.slideshow_task = asyncio.create_task(self._slideshow_loop())
        
        await self._notify_status_change({
            'type': 'slideshow_started',
            'started_at': self.slideshow_stats['started_at'].isoformat()
        })
        
        return True
    
    async def stop_slideshow(self) -> bool:
        """Stop the slideshow"""
        if not self.is_running:
            return False
        
        self.is_running = False
        
        # Cancel slideshow task
        if self.slideshow_task:
            self.slideshow_task.cancel()
            try:
                await self.slideshow_task
            except asyncio.CancelledError:
                pass
            self.slideshow_task = None
        
        # Stop playback on all devices
        await self.airplay_manager.stop_playback_on_all_devices()
        
        self.logger.info("Slideshow stopped")
        
        await self._notify_status_change({
            'type': 'slideshow_stopped',
            'stopped_at': datetime.now().isoformat(),
            'stats': self.slideshow_stats
        })
        
        return True
    
    async def _slideshow_loop(self):
        """Main slideshow loop"""
        try:
            if self.video_mode:
                # Video mode: create and stream video files
                await self._video_slideshow_loop()
            else:
                # Image mode: stream individual images
                await self._image_slideshow_loop()
                
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.error(f"Slideshow loop error: {e}")
            await self._notify_error(f"Slideshow error: {e}")
            self.is_running = False
    
    async def _image_slideshow_loop(self):
        """Image-based slideshow loop"""
        while self.is_running:
            # Get current image distribution
            distribution = self.distribute_images_to_devices(
                self.active_devices, 
                self.current_images, 
                self.current_image_index
            )
            
            if not distribution:
                self.logger.error("No image distribution created")
                break
            
            # Stream images to devices
            self.logger.info(f"Displaying images: index {self.current_image_index}, distribution: {list(distribution.values())}")
            
            results = await self.airplay_manager.stream_images_to_devices(distribution)
            
            # Check for errors
            failed_devices = [device_id for device_id, success in results.items() if not success]
            if failed_devices:
                self.slideshow_stats['errors'] += len(failed_devices)
                for device_id in failed_devices:
                    await self._notify_error(f"Failed to display image on device", device_id)
                    
                    # Attempt reconnection
                    asyncio.create_task(self.device_manager.reconnect_device(device_id))
            
            # Update statistics
            successful_displays = sum(1 for success in results.values() if success)
            self.slideshow_stats['images_displayed'] += successful_displays
            
            # Move to next set of images
            self.current_image_index += len(self.active_devices)
            
            # Check if we've completed a cycle
            if self.current_image_index >= len(self.current_images):
                self.current_image_index = 0
                self.slideshow_stats['cycles_completed'] += 1
                
                await self._notify_status_change({
                    'type': 'cycle_completed',
                    'cycles': self.slideshow_stats['cycles_completed']
                })
            
            # Notify status update
            stats_serializable = {
                'started_at': self.slideshow_stats['started_at'].isoformat() if self.slideshow_stats['started_at'] else None,
                'images_displayed': self.slideshow_stats['images_displayed'],
                'cycles_completed': self.slideshow_stats['cycles_completed'],
                'errors': self.slideshow_stats['errors']
            }
            await self._notify_status_change({
                'type': 'images_displayed',
                'current_index': self.current_image_index,
                'distribution': {device_id: Path(path).name for device_id, path in distribution.items()},
                'stats': stats_serializable
            })
            
            # Wait for display time
            await asyncio.sleep(self.display_time)
    
    async def _video_slideshow_loop(self):
        """Video-based slideshow loop"""
        # Create video for each device with unique image set
        video_paths = {}
        
        for i, device_id in enumerate(self.active_devices):
            # Get unique set of images for this device (round-robin)
            device_images = []
            num_images = len(self.current_images)
            for j in range(num_images):
                image_index = (i + j * len(self.active_devices)) % num_images
                device_images.append(self.current_images[image_index])
            
            # Create slideshow ID for this device
            slideshow_id = f"device_{device_id}_{len(device_images)}images"
            
            self.logger.info(f"Creating video for device {device_id} with {len(device_images)} images")
            
            # Create video
            video_path = await self.video_creator.create_slideshow_video(
                image_paths=device_images,
                slideshow_id=slideshow_id,
                duration_per_image=self.display_time,
                transition_duration=self.transition_duration,
                use_transitions=True
            )
            
            if video_path:
                video_paths[device_id] = video_path
                self.logger.info(f"Video created for device {device_id}: {video_path}")
            else:
                self.logger.error(f"Failed to create video for device {device_id}")
                await self._notify_error(f"Failed to create video for device {device_id}")
        
        if not video_paths:
            self.logger.error("No videos were created successfully")
            return
        
        # Stream videos to devices concurrently
        self.logger.info(f"Streaming videos to {len(video_paths)} devices")
        
        results = await self.airplay_manager.stream_videos_to_devices(video_paths)
        
        # Check results
        failed_devices = [device_id for device_id, success in results.items() if not success]
        if failed_devices:
            self.slideshow_stats['errors'] += len(failed_devices)
            for device_id in failed_devices:
                await self._notify_error(f"Failed to stream video to device {device_id}")
        
        successful_streams = sum(1 for success in results.values() if success)
        self.slideshow_stats['images_displayed'] += successful_streams
        
        # Notify status
        await self._notify_status_change({
            'type': 'video_slideshow_started',
            'devices_streaming': len(video_paths),
            'successful_streams': successful_streams,
            'failed_streams': len(failed_devices)
        })
        
        # Calculate total duration for one cycle through all images
        total_duration = len(self.current_images) * self.display_time
        
        self.logger.info(f"Video slideshow running for {total_duration}s per cycle")
        
        # Monitor and restart video cycles
        try:
            while self.is_running:
                # Wait for current video cycle to complete
                await asyncio.sleep(total_duration + 5)  # Add 5s buffer for transitions
                
                if not self.is_running:
                    break
                
                # Update cycle stats
                self.slideshow_stats['cycles_completed'] += 1
                self.slideshow_stats['images_displayed'] += len(self.current_images) * successful_streams
                
                await self._notify_status_change({
                    'type': 'cycle_completed',
                    'cycles': self.slideshow_stats['cycles_completed'],
                    'total_images_displayed': self.slideshow_stats['images_displayed']
                })
                
                # Restart video streaming for next cycle
                self.logger.info(f"Starting video cycle {self.slideshow_stats['cycles_completed'] + 1}")
                
                # Re-stream the same videos (they loop automatically)
                results = await self.airplay_manager.stream_videos_to_devices(video_paths)
                
                # Check for any devices that failed this cycle
                current_failed = [device_id for device_id, success in results.items() if not success]
                if current_failed:
                    self.slideshow_stats['errors'] += len(current_failed)
                    for device_id in current_failed:
                        await self._notify_error(f"Failed to restart video on device {device_id}")
                        # Attempt device reconnection
                        asyncio.create_task(self.device_manager.reconnect_device(device_id))
                
                # Brief status update
                await self._notify_status_change({
                    'type': 'video_slideshow_running',
                    'devices_streaming': len([d for d, s in results.items() if s])
                })
                
        except asyncio.CancelledError:
            raise
    
    async def next_images(self) -> bool:
        """Manually advance to next set of images"""
        if not self.is_running:
            return False
        
        # This will be picked up in the next loop iteration
        self.current_image_index += len(self.active_devices)
        if self.current_image_index >= len(self.current_images):
            self.current_image_index = 0
        
        return True
    
    async def previous_images(self) -> bool:
        """Manually go back to previous set of images"""
        if not self.is_running:
            return False
        
        self.current_image_index -= len(self.active_devices)
        if self.current_image_index < 0:
            # Go to last complete set
            num_complete_sets = len(self.current_images) // len(self.active_devices)
            self.current_image_index = (num_complete_sets - 1) * len(self.active_devices)
            if self.current_image_index < 0:
                self.current_image_index = 0
        
        return True
    
    async def update_display_time(self, new_display_time: int) -> bool:
        """Update display time during slideshow"""
        if new_display_time <= 0:
            return False
        
        self.display_time = new_display_time
        self.logger.info(f"Updated display time to {new_display_time} seconds")
        
        await self._notify_status_change({
            'type': 'display_time_updated',
            'display_time': new_display_time
        })
        
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get current slideshow status"""
        return {
            'is_running': self.is_running,
            'images_directory': self.current_images_directory,
            'images_count': len(self.current_images) if self.current_images else 0,
            'active_devices': self.active_devices,
            'display_time': self.display_time,
            'current_index': self.current_image_index,
            'video_mode': self.video_mode,
            'transition_duration': self.transition_duration,
            'stats': self.slideshow_stats,
            'connected_devices': self.device_manager.get_connected_devices()
        }
    
    async def load_last_session(self) -> bool:
        """Load the last slideshow session from database"""
        try:
            session = await self.db_manager.get_last_slideshow_session()
            if session:
                success = await self.configure_slideshow(
                    images_directory=session['images_directory'],
                    devices=session['active_devices'],
                    display_time=session['display_time']
                )
                if success:
                    self.logger.info("Loaded last slideshow session")
                return success
            return False
        except Exception as e:
            self.logger.error(f"Error loading last session: {e}")
            return False