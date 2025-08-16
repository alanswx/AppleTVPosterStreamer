#!/usr/bin/env python3

import asyncio
import pyatv
from pyatv.const import Protocol
from device_manager import DeviceManager
from database import DatabaseManager

async def test_streaming_methods():
    """Test different methods for streaming to AirPlay devices"""
    
    # Initialize and connect to a device
    db_manager = DatabaseManager()
    await db_manager.init_database()
    device_manager = DeviceManager(db_manager)
    
    # Use the device that's been giving us trouble
    device_id = "4A:94:50:D7:12:D0"
    
    print(f"Testing streaming methods for device {device_id}")
    
    # Connect to the device
    success = await device_manager.connect_to_device(device_id)
    if not success:
        print("Failed to connect to device")
        return
    
    connection = device_manager.get_device_connection(device_id)
    if not connection:
        print("No connection found")
        return
    
    print("Connected successfully!")
    print(f"Connection type: {type(connection)}")
    print(f"Stream interface: {type(connection.stream)}")
    
    # Check available methods on the stream interface
    stream_methods = [method for method in dir(connection.stream) if not method.startswith('_')]
    print(f"Available stream methods: {stream_methods}")
    
    # Test what's available
    for method_name in stream_methods:
        method = getattr(connection.stream, method_name)
        if callable(method):
            print(f"  {method_name}: {method.__doc__ or 'No documentation'}")
    
    # Try specific methods
    try:
        print("\nTesting play_url...")
        await connection.stream.play_url("http://httpbin.org/status/200")
        print("play_url works!")
    except Exception as e:
        print(f"play_url failed: {e}")
    
    # Check if there are other interfaces
    print(f"\nConnection interfaces:")
    interfaces = [attr for attr in dir(connection) if not attr.startswith('_')]
    for interface_name in interfaces:
        interface = getattr(connection, interface_name)
        if hasattr(interface, '__call__') or hasattr(interface, '__dict__'):
            print(f"  {interface_name}: {type(interface)}")
    
    # Check for features
    if hasattr(connection, 'features'):
        features = connection.features
        print(f"\nDevice features: {features}")
    
    await device_manager.disconnect_device(device_id)

if __name__ == "__main__":
    asyncio.run(test_streaming_methods())