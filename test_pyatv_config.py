#!/usr/bin/env python3

import pyatv
from pyatv.const import Protocol

# Test the correct API for pyatv config creation
print("Testing pyatv.conf.AppleTV constructor...")

try:
    # Try different constructor patterns
    print("1. Trying with just address and name:")
    config1 = pyatv.conf.AppleTV(address="10.0.2.117", name="Test Device")
    print("  Success!")
except Exception as e:
    print(f"  Failed: {e}")

try:
    print("2. Trying with empty properties:")
    config2 = pyatv.conf.AppleTV(address="10.0.2.117", name="Test Device", properties={})
    print("  Success!")
except Exception as e:
    print(f"  Failed: {e}")

try:
    print("3. Trying with identifier in properties:")
    config3 = pyatv.conf.AppleTV(
        address="10.0.2.117", 
        name="Test Device", 
        properties={"identifier": "test-id"}
    )
    print("  Success!")
except Exception as e:
    print(f"  Failed: {e}")

try:
    print("4. Trying ManualService creation:")
    service = pyatv.conf.ManualService(
        identifier="test-service",
        protocol=Protocol.AirPlay,
        port=7000
    )
    print("  Success!")
except Exception as e:
    print(f"  Failed: {e}")

# Test what works for creating an Apple TV config
print("\n5. Testing working configuration:")
try:
    device_config = pyatv.conf.AppleTV(
        address="10.0.2.117",
        name="Test Device", 
        properties={}
    )
    
    airplay_service = pyatv.conf.ManualService(
        identifier="test-device",
        protocol=Protocol.AirPlay,
        port=7000
    )
    
    device_config.add_service(airplay_service)
    print("  Complete config created successfully!")
    print(f"  Config: {device_config}")
    
except Exception as e:
    print(f"  Failed: {e}")