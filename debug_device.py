#!/usr/bin/env python3
"""
Debug script to test Apple TV device connection and capabilities
"""

import asyncio
import sys
from device_manager import DeviceManager
from database import DatabaseManager
from airplay_manager import AirPlayStreamManager

async def debug_device(device_id):
    """Debug a specific device"""
    print(f"🔍 Debugging device: {device_id}")
    
    # Initialize managers
    db_manager = DatabaseManager()
    await db_manager.init_database()
    
    device_manager = DeviceManager(db_manager)
    airplay_manager = AirPlayStreamManager(device_manager)
    
    try:
        # Check if device is connected
        print(f"📱 Is device connected: {device_manager.is_device_connected(device_id)}")
        
        # Get device info
        device_info = await device_manager.get_device_info(device_id)
        if device_info:
            print(f"📋 Device info: {device_info}")
        else:
            print("❌ Device not found in database")
            return
        
        # Try to connect if not connected
        if not device_manager.is_device_connected(device_id):
            print("🔌 Attempting to connect...")
            success = await device_manager.connect_to_device(device_id)
            print(f"🔌 Connection result: {success}")
        
        # Get connection object
        connection = device_manager.get_device_connection(device_id)
        if connection:
            print("✅ Got connection object")
            
            # Diagnose capabilities
            diagnosis = await airplay_manager.diagnose_device_capabilities(device_id)
            print(f"🔬 Device capabilities: {diagnosis}")
            
            # Check pairing requirements
            pairing_info = await airplay_manager.check_airplay_pairing_required(device_id)
            print(f"🔐 Pairing info: {pairing_info}")
            
            # Test a simple video URL
            test_url = "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
            print(f"🎥 Testing with sample video: {test_url}")
            
            try:
                await connection.stream.play_url(test_url)
                print("✅ Sample video streaming started successfully!")
            except Exception as e:
                print(f"❌ Sample video streaming failed: {e}")
        else:
            print("❌ No connection object available")
            
    except Exception as e:
        print(f"💥 Error during debugging: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        await device_manager.disconnect_all_devices()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python debug_device.py <device_id>")
        print("Example: python debug_device.py CE:50:AA:56:9C:69")
        sys.exit(1)
    
    device_id = sys.argv[1]
    asyncio.run(debug_device(device_id))