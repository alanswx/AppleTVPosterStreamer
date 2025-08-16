import os
import tempfile
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
import asyncio
import threading

class VideoCreator:
    """Creates video files from image slideshows with transitions"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.temp_video_dir = tempfile.mkdtemp(prefix='airplay_videos_')
        self.generated_videos: Dict[str, str] = {}
        self.progress_callback = None
        
    def set_progress_callback(self, callback):
        """Set callback function for progress updates"""
        self.progress_callback = callback
        
    def check_dependencies(self) -> Dict[str, bool]:
        """Check if required video libraries are available"""
        deps = {
            'moviepy': False,
            'opencv': False,
            'ffmpeg': False,
            'pillow': True  # Already used in the project
        }
        
        try:
            import moviepy
            deps['moviepy'] = True
        except ImportError:
            pass
            
        try:
            import cv2
            deps['opencv'] = True
        except ImportError:
            pass
            
        try:
            import subprocess
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, timeout=5)
            deps['ffmpeg'] = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
            
        return deps
    
    def install_moviepy_command(self) -> str:
        """Return command to install MoviePy"""
        return "pip install moviepy"
        
    async def _monitor_video_progress(self, total_frames: int, total_duration: float):
        """Monitor video creation progress with time-based estimation"""
        start_time = asyncio.get_event_loop().time()
        update_interval = 1.0  # Update every second
        
        while True:
            await asyncio.sleep(update_interval)
            elapsed_time = asyncio.get_event_loop().time() - start_time
            
            # Estimate progress based on elapsed time (assume video creation takes ~2x video duration)
            estimated_total_time = total_duration * 2
            progress_ratio = min(elapsed_time / estimated_total_time, 0.95)  # Cap at 95% until completion
            estimated_frame = int(total_frames * progress_ratio)
            
            if self.progress_callback:
                await self.progress_callback({
                    'stage': 'creating',
                    'current_frame': estimated_frame,
                    'total_frames': total_frames
                })
    
    async def create_slideshow_video_moviepy(
        self, 
        image_paths: List[str],
        output_path: str,
        duration_per_image: float = 5.0,
        transition_duration: float = 1.0,
        video_size: tuple = (1920, 1080),
        fps: int = 24
    ) -> bool:
        """
        Create slideshow video using MoviePy with fade transitions
        
        Args:
            image_paths: List of image file paths
            output_path: Output video file path
            duration_per_image: Seconds to display each image
            transition_duration: Seconds for fade transition
            video_size: Output video resolution (width, height)
            fps: Frames per second
        """
        try:
            from moviepy import ImageClip, concatenate_videoclips
            # from moviepy.video.fx import resize
            
            if not image_paths:
                self.logger.error("No images provided for video creation")
                return False
                
            clips = []
            
            for i, image_path in enumerate(image_paths):
                if not os.path.exists(image_path):
                    self.logger.warning(f"Image not found: {image_path}")
                    continue
                    
                # Create image clip
                clip = ImageClip(image_path, duration=duration_per_image)
                
                # Resize to target size while maintaining aspect ratio  
                clip = clip.resized(new_size=video_size)
                
                # Note: Fade effects temporarily disabled for MoviePy 2.x compatibility
                # This can be added back when the effects API is clarified
                
                clips.append(clip)
            
            if not clips:
                self.logger.error("No valid images found for video creation")
                return False
            
            # Concatenate all clips
            final_video = concatenate_videoclips(clips, method="compose")
            
            # Calculate total frames for progress tracking
            total_duration = len(image_paths) * duration_per_image + (len(image_paths) - 1) * transition_duration
            total_frames = int(total_duration * fps)
            
            # Send progress callback
            if self.progress_callback:
                await self.progress_callback({
                    'stage': 'starting',
                    'total_frames': total_frames,
                    'current_frame': 0
                })
            
            # Run video creation with progress estimation
            loop = asyncio.get_event_loop()
            
            # Start progress monitoring task
            progress_task = None
            if self.progress_callback:
                progress_task = asyncio.create_task(
                    self._monitor_video_progress(total_frames, total_duration)
                )
            
            try:
                # Run video creation
                await loop.run_in_executor(
                    None, 
                    lambda: final_video.write_videofile(
                        output_path,
                        fps=fps,
                        codec='libx264'
                    )
                )
            finally:
                # Cancel progress monitoring
                if progress_task:
                    progress_task.cancel()
                    try:
                        await progress_task
                    except asyncio.CancelledError:
                        pass
            
            # Send completion callback
            if self.progress_callback:
                await self.progress_callback({
                    'stage': 'completed',
                    'total_frames': total_frames,
                    'current_frame': total_frames
                })
            
            # Clean up
            final_video.close()
            for clip in clips:
                clip.close()
                
            self.logger.info(f"Successfully created video: {output_path}")
            return True
            
        except ImportError:
            self.logger.error("MoviePy not installed. Run: pip install moviepy")
            return False
        except Exception as e:
            self.logger.error(f"Error creating video with MoviePy: {e}")
            # Send error callback
            if self.progress_callback:
                await self.progress_callback({
                    'stage': 'error',
                    'error': str(e)
                })
            return False
    
    async def create_slideshow_video_opencv(
        self,
        image_paths: List[str],
        output_path: str,
        duration_per_image: float = 5.0,
        video_size: tuple = (1920, 1080),
        fps: int = 24
    ) -> bool:
        """
        Create slideshow video using OpenCV (simpler, no transitions)
        
        Args:
            image_paths: List of image file paths
            output_path: Output video file path
            duration_per_image: Seconds to display each image
            video_size: Output video resolution (width, height)
            fps: Frames per second
        """
        try:
            import cv2
            import numpy as np
            from PIL import Image
            
            if not image_paths:
                self.logger.error("No images provided for video creation")
                return False
            
            # Initialize video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, video_size)
            
            frames_per_image = int(duration_per_image * fps)
            
            for image_path in image_paths:
                if not os.path.exists(image_path):
                    self.logger.warning(f"Image not found: {image_path}")
                    continue
                
                # Load and resize image
                with Image.open(image_path) as pil_img:
                    # Convert to RGB if needed
                    if pil_img.mode != 'RGB':
                        pil_img = pil_img.convert('RGB')
                    
                    # Resize to fit video dimensions
                    pil_img.thumbnail(video_size, Image.Resampling.LANCZOS)
                    
                    # Create black background
                    background = Image.new('RGB', video_size, 'black')
                    
                    # Center the image on background
                    x = (video_size[0] - pil_img.width) // 2
                    y = (video_size[1] - pil_img.height) // 2
                    background.paste(pil_img, (x, y))
                    
                    # Convert to OpenCV format
                    frame = cv2.cvtColor(np.array(background), cv2.COLOR_RGB2BGR)
                
                # Write frames for this image
                for _ in range(frames_per_image):
                    out.write(frame)
            
            out.release()
            
            self.logger.info(f"Successfully created video: {output_path}")
            return True
            
        except ImportError:
            self.logger.error("OpenCV not installed. Run: pip install opencv-python")
            return False
        except Exception as e:
            self.logger.error(f"Error creating video with OpenCV: {e}")
            return False
    
    async def create_slideshow_video(
        self,
        image_paths: List[str],
        slideshow_id: str,
        duration_per_image: float = 5.0,
        transition_duration: float = 1.0,
        use_transitions: bool = True
    ) -> Optional[str]:
        """
        Create slideshow video with automatic library selection
        
        Args:
            image_paths: List of image file paths
            slideshow_id: Unique identifier for this slideshow
            duration_per_image: Seconds to display each image
            transition_duration: Seconds for fade transition (MoviePy only)
            use_transitions: Whether to use fade transitions
            
        Returns:
            Path to created video file, or None if failed
        """
        if not image_paths:
            return None
            
        # Generate output path
        output_filename = f"slideshow_{slideshow_id}_{len(image_paths)}images.mp4"
        output_path = os.path.join(self.temp_video_dir, output_filename)
        
        # Check if already exists
        if slideshow_id in self.generated_videos:
            existing_path = self.generated_videos[slideshow_id]
            if os.path.exists(existing_path):
                self.logger.info(f"Using existing video: {existing_path}")
                return existing_path
        
        # Check available libraries
        deps = self.check_dependencies()
        
        success = False
        
        # Try MoviePy first (best for transitions)
        if use_transitions and deps['moviepy']:
            self.logger.info("Creating video with MoviePy (with transitions)")
            success = await self.create_slideshow_video_moviepy(
                image_paths, output_path, duration_per_image, transition_duration
            )
        
        # Fallback to OpenCV
        elif deps['opencv']:
            self.logger.info("Creating video with OpenCV (no transitions)")
            success = await self.create_slideshow_video_opencv(
                image_paths, output_path, duration_per_image
            )
            
        else:
            self.logger.error("No suitable video creation library found")
            self.logger.error("Install MoviePy: pip install moviepy")
            self.logger.error("Or install OpenCV: pip install opencv-python")
            return None
        
        if success and os.path.exists(output_path):
            self.generated_videos[slideshow_id] = output_path
            return output_path
        else:
            return None
    
    def get_video_url(self, slideshow_id: str, base_url: str) -> Optional[str]:
        """Get URL for serving the video file"""
        if slideshow_id in self.generated_videos:
            video_path = self.generated_videos[slideshow_id]
            filename = os.path.basename(video_path)
            return f"{base_url}/video/{filename}"
        return None
    
    def cleanup(self):
        """Clean up temporary video files"""
        try:
            import shutil
            if os.path.exists(self.temp_video_dir):
                shutil.rmtree(self.temp_video_dir)
                self.logger.info("Cleaned up temporary video files")
        except Exception as e:
            self.logger.error(f"Error cleaning up video files: {e}")
    
    def get_video_info(self, slideshow_id: str) -> Optional[Dict[str, Any]]:
        """Get information about generated video"""
        if slideshow_id not in self.generated_videos:
            return None
            
        video_path = self.generated_videos[slideshow_id]
        if not os.path.exists(video_path):
            return None
            
        try:
            stat = os.stat(video_path)
            return {
                'path': video_path,
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'created': stat.st_ctime,
                'exists': True
            }
        except Exception:
            return None