#!/usr/bin/env python3

import asyncio
import json
from device_manager import DeviceManager
from database import DatabaseManager

async def test_scan_api():
    """Test the scan devices API response format"""
    print("Testing device scan API response format...")
    
    # Initialize managers
    db_manager = DatabaseManager()
    await db_manager.init_database()
    device_manager = DeviceManager(db_manager)
    
    # Scan for devices
    devices = await device_manager.scan_for_devices()
    
    # Format as API response
    api_response = {
        'success': True,
        'devices': devices
    }
    
    print(f"API Response:")
    print(json.dumps(api_response, indent=2))
    
    print(f"\nFirst device structure:")
    if devices:
        print(json.dumps(devices[0], indent=2))
    
    # Test what frontend expects
    print(f"\nFrontend device processing test:")
    for device in devices:
        print(f"device_id: {device.get('device_id')}")
        print(f"name: {device.get('name')}")
        print(f"is_active: {device.get('is_active', False)}")
        print("---")

if __name__ == "__main__":
    asyncio.run(test_scan_api())