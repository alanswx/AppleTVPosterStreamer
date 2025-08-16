#!/usr/bin/env python3

import pyatv
from pyatv.const import Protocol

print("Testing ManualService constructor...")

try:
    print("1. Testing ManualService with properties:")
    service = pyatv.conf.ManualService(
        properties={"identifier": "test-service"},
        protocol=Protocol.AirPlay,
        port=7000
    )
    print("  Success!")
except Exception as e:
    print(f"  Failed: {e}")

try:
    print("2. Testing ManualService with empty properties:")
    service = pyatv.conf.ManualService(
        properties={},
        protocol=Protocol.AirPlay,
        port=7000
    )
    print("  Success!")
except Exception as e:
    print(f"  Failed: {e}")

try:
    print("3. Full working example:")
    device_config = pyatv.conf.AppleTV(
        address="10.0.2.117",
        name="Test Device"
    )
    
    airplay_service = pyatv.conf.ManualService(
        properties={"identifier": "test-device"},
        protocol=Protocol.AirPlay,
        port=7000
    )
    
    device_config.add_service(airplay_service)
    print("  Complete config created successfully!")
    
except Exception as e:
    print(f"  Failed: {e}")

# Let's also check what parameters ManualService actually expects
print("\n4. Checking ManualService signature:")
import inspect
sig = inspect.signature(pyatv.conf.ManualService.__init__)
print(f"ManualService.__init__ signature: {sig}")

print("\n5. Checking AppleTV signature:")
sig2 = inspect.signature(pyatv.conf.AppleTV.__init__)
print(f"AppleTV.__init__ signature: {sig2}")