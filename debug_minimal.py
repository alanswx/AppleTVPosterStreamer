#!/usr/bin/env python3
"""
Minimal debugging script to test each component separately
"""

import asyncio
import json
from flask import Flask, jsonify
import threading
import time

# Test 1: Direct device scan
async def test_device_scan():
    print("=== TEST 1: Device Scan ===")
    from device_manager import DeviceManager
    from database import DatabaseManager
    
    db_manager = DatabaseManager()
    await db_manager.init_database()
    device_manager = DeviceManager(db_manager)
    
    devices = await device_manager.scan_for_devices()
    print(f"Found {len(devices)} devices")
    if devices:
        print("First device:", json.dumps(devices[0], indent=2))
    return devices

# Test 2: Flask API endpoint
def test_flask_api(devices):
    print("\n=== TEST 2: Flask API Response ===")
    
    app = Flask(__name__)
    
    @app.route('/test-scan', methods=['GET'])
    def test_scan():
        return jsonify({'success': True, 'devices': devices})
    
    @app.route('/test-empty', methods=['GET'])
    def test_empty():
        return jsonify({'success': True, 'devices': []})
    
    # Run Flask in background
    def run_flask():
        app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(1)  # Let Flask start
    
    # Test the endpoints
    import requests
    try:
        print("Testing /test-scan endpoint...")
        response = requests.get('http://127.0.0.1:5001/test-scan', timeout=5)
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: success={data.get('success')}, devices_count={len(data.get('devices', []))}")
        
        print("Testing /test-empty endpoint...")
        response = requests.get('http://127.0.0.1:5001/test-empty', timeout=5)
        print(f"Empty response: {response.json()}")
        
    except Exception as e:
        print(f"Flask test failed: {e}")

# Test 3: HTML/JS simulation
def test_frontend_logic(devices):
    print("\n=== TEST 3: Frontend Logic Simulation ===")
    
    # Simulate what JavaScript does
    devices_map = {}
    for device in devices:
        devices_map[device['device_id']] = device
    
    print(f"Devices map size: {len(devices_map)}")
    
    # Simulate updateDevicesDisplay logic
    if len(devices_map) == 0:
        print("Would show: 'No devices found' message")
    else:
        print("Would show device cards:")
        for i, (device_id, device) in enumerate(devices_map.items()):
            if i < 3:  # Show first 3
                status = "connected" if device.get('is_active') else "disconnected"
                print(f"  - {device['name']} ({status})")

async def main():
    print("Starting comprehensive debug test...\n")
    
    # Test device scanning
    devices = await test_device_scan()
    
    # Test Flask API
    test_flask_api(devices)
    
    # Test frontend logic
    test_frontend_logic(devices)
    
    print("\n=== SUMMARY ===")
    print(f"- Device scan: {'✓' if devices else '✗'}")
    print(f"- Device count: {len(devices)}")
    print(f"- Has is_active field: {'✓' if devices and 'is_active' in devices[0] else '✗'}")

if __name__ == "__main__":
    asyncio.run(main())