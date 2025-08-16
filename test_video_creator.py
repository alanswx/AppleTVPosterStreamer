#!/usr/bin/env python3

import asyncio
import os
import glob
from video_creator import VideoCreator

async def test_video_creation():
    """Test video creation functionality"""
    
    # Initialize video creator
    creator = VideoCreator()
    
    # Check dependencies
    deps = creator.check_dependencies()
    print("Dependencies:")
    for lib, available in deps.items():
        status = "✓" if available else "✗"
        print(f"  {status} {lib}")
    
    if not (deps['moviepy'] or deps['opencv']):
        print("\nNo video libraries available. Install with:")
        print("pip install moviepy opencv-python")
        return
    
    # Find some test images
    image_dir = "images"
    if os.path.exists(image_dir):
        image_patterns = ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]
        image_paths = []
        
        for pattern in image_patterns:
            image_paths.extend(glob.glob(os.path.join(image_dir, pattern)))
        
        # Limit to first 5 images for testing
        image_paths = image_paths[:5]
        
        if image_paths:
            print(f"\nFound {len(image_paths)} test images:")
            for img in image_paths:
                print(f"  - {img}")
            
            # Test video creation
            print("\nCreating test video...")
            video_path = await creator.create_slideshow_video(
                image_paths=image_paths,
                slideshow_id="test_slideshow",
                duration_per_image=3.0,  # Shorter for testing
                transition_duration=0.5,
                use_transitions=True
            )
            
            if video_path:
                print(f"✓ Video created successfully: {video_path}")
                
                # Get video info
                info = creator.get_video_info("test_slideshow")
                if info:
                    print(f"  - Size: {info['size_mb']} MB")
                    print(f"  - Path: {info['path']}")
                
                # Test URL generation
                base_url = "http://localhost:8080"
                video_url = creator.get_video_url("test_slideshow", base_url)
                if video_url:
                    print(f"  - URL: {video_url}")
                
            else:
                print("✗ Video creation failed")
        else:
            print(f"\nNo images found in {image_dir} directory")
    else:
        print(f"\nImages directory '{image_dir}' not found")
    
    # Cleanup
    print("\nCleaning up...")
    creator.cleanup()
    print("✓ Test completed")

if __name__ == "__main__":
    asyncio.run(test_video_creation())