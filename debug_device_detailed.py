#!/usr/bin/env python3
"""
Enhanced debug script to analyze Apple TV device capabilities and pairing requirements
"""

import asyncio
import sys
import pyatv
from pyatv.const import Protocol, PairingRequirement, FeatureName, FeatureState

async def debug_device_detailed(device_id):
    """Comprehensive device debugging"""
    print(f"🔍 Detailed debugging for device: {device_id}")
    print("=" * 60)
    
    try:
        # Scan for the specific device
        print("🔎 Scanning for device...")
        atvs = await pyatv.scan(identifier=device_id, timeout=10, loop=asyncio.get_event_loop())
        if not atvs:
            print("❌ Device not found during scan")
            return
        
        config = atvs[0]
        print(f"✅ Found device: {config.name} at {config.address}")
        
        # === DEVICE INFORMATION ===
        print("\n📱 DEVICE INFORMATION")
        print("-" * 30)
        
        atv = await pyatv.connect(config, loop=asyncio.get_event_loop())
        try:
            devinfo = atv.device_info
            print(f"Operating System: {devinfo.operating_system}")
            print(f"Version: {devinfo.version}")
            print(f"Build: {devinfo.build}")
            print(f"Model: {devinfo.model}")
            print(f"MAC Address: {devinfo.mac}")
        except Exception as e:
            print(f"Could not get device info: {e}")
        finally:
            atv.close()
        
        # === SERVICE ANALYSIS ===
        print(f"\n🔧 SERVICE ANALYSIS")
        print("-" * 30)
        print(f"Total services: {len(config.services)}")
        
        airplay_service = None
        for service in config.services:
            print(f"\n🔸 Protocol: {service.protocol}")
            print(f"   Port: {service.port}")
            print(f"   Enabled: {service.enabled}")
            print(f"   Pairing Requirement: {service.pairing}")
            print(f"   Has Credentials: {bool(service.credentials)}")
            print(f"   Properties: {service.properties}")
            
            if service.protocol == Protocol.AirPlay:
                airplay_service = service
        
        # === AIRPLAY ANALYSIS ===
        if airplay_service:
            print(f"\n🎥 AIRPLAY SERVICE ANALYSIS")
            print("-" * 30)
            print(f"AirPlay Port: {airplay_service.port}")
            print(f"AirPlay Pairing: {airplay_service.pairing}")
            print(f"AirPlay Properties: {airplay_service.properties}")
            
            # Check pairing capability
            if airplay_service.pairing in [PairingRequirement.Optional, PairingRequirement.Mandatory]:
                print("✅ AirPlay pairing is supported")
                try:
                    pairing = await pyatv.pair(config, Protocol.AirPlay)
                    print(f"✅ Pairing handler created successfully")
                    print(f"   Device provides PIN: {pairing.device_provides_pin}")
                    await pairing.close()
                except Exception as e:
                    print(f"❌ Pairing creation failed: {e}")
            elif airplay_service.pairing == PairingRequirement.Disabled:
                print("⚠️  AirPlay pairing is disabled - check device settings")
            elif airplay_service.pairing == PairingRequirement.NotNeeded:
                print("ℹ️  AirPlay pairing is not required")
            else:
                print("❌ AirPlay pairing is not supported")
        else:
            print(f"\n❌ NO AIRPLAY SERVICE FOUND")
        
        # === FEATURE ANALYSIS ===
        print(f"\n⚙️  FEATURE ANALYSIS")
        print("-" * 30)
        
        atv = await pyatv.connect(config, loop=asyncio.get_event_loop())
        try:
            features = atv.features
            
            # Check specific streaming features
            play_url_feature = features.get_feature(FeatureName.PlayUrl)
            stream_file_feature = features.get_feature(FeatureName.StreamFile)
            
            print(f"PlayUrl state: {play_url_feature.state}")
            print(f"StreamFile state: {stream_file_feature.state}")
            
            # Show all stream-related features
            all_features = features.all_features(include_unsupported=True)
            stream_features = {k: v for k, v in all_features.items() 
                              if any(word in k.name.lower() for word in ['stream', 'play', 'url', 'file'])}
            
            if stream_features:
                print(f"\nStream-related features:")
                for name, feature in stream_features.items():
                    print(f"  {name.name}: {feature.state.name}")
            
            # Show all available features
            available_features = {k: v for k, v in all_features.items() 
                                if v.state == FeatureState.Available}
            print(f"\nAll available features ({len(available_features)}):")
            for name, feature in available_features.items():
                print(f"  {name.name}")
                
        except Exception as e:
            print(f"Error analyzing features: {e}")
        finally:
            atv.close()
        
        # === STREAMING TEST ===
        print(f"\n🎬 STREAMING TEST")
        print("-" * 30)
        
        atv = await pyatv.connect(config, loop=asyncio.get_event_loop())
        try:
            # Test with a known working video URL
            test_url = "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
            print(f"Testing URL: {test_url}")
            
            await atv.stream.play_url(test_url)
            print("✅ Stream test successful!")
            
            # Wait a moment then check if it's playing
            await asyncio.sleep(2)
            
            # Try to get playing status
            try:
                playing = atv.metadata.playing()
                print(f"Playing status: {playing}")
            except:
                print("Could not get playing status")
                
        except Exception as e:
            error_msg = str(e).lower()
            if "not supported" in error_msg:
                print("❌ play_url is not supported by this device")
                print("   This may indicate:")
                print("   - Older Apple TV model (2nd/3rd generation)")
                print("   - AirPlay access restrictions enabled")
                print("   - Device requires pairing that hasn't been completed")
            elif "unavailable" in error_msg:
                print("⚠️  play_url is temporarily unavailable")
                print("   This may indicate:")
                print("   - Device requires authentication")
                print("   - AirPlay access is restricted")
                print("   - Device is in wrong state")
            else:
                print(f"❌ Stream test failed: {e}")
        finally:
            atv.close()
        
        # === RECOMMENDATIONS ===
        print(f"\n💡 RECOMMENDATIONS")
        print("-" * 30)
        
        if airplay_service:
            if airplay_service.pairing == PairingRequirement.Disabled:
                print("1. Check Apple TV Settings > AirPlay and HomeKit")
                print("   - Set 'Allow Access' to 'Anyone on the Same Network'")
                print("   - Ensure device is assigned to a room")
            elif airplay_service.pairing in [PairingRequirement.Optional, PairingRequirement.Mandatory]:
                print("1. Complete AirPlay pairing using the web interface")
                print("2. Or use: atvremote --id {device_id} --protocol airplay pair")
            elif play_url_feature.state == FeatureState.Unavailable:
                print("1. Device supports play_url but it's currently unavailable")
                print("2. Check AirPlay access settings on the device")
                print("3. Try restarting the Apple TV")
        else:
            print("1. No AirPlay service found - this device may not support AirPlay streaming")
            print("2. Try connecting with different protocols")
        
        print(f"\n🎯 CONCLUSION")
        print("-" * 30)
        
        if airplay_service and play_url_feature.state in [FeatureState.Available, FeatureState.Unavailable]:
            print("✅ Device appears to support AirPlay video streaming")
            if play_url_feature.state == FeatureState.Unavailable:
                print("⚠️  But requires configuration/pairing to enable it")
        else:
            print("❌ Device may not support AirPlay video streaming")
            print("   Consider using a newer Apple TV model for reliable video streaming")
            
    except Exception as e:
        print(f"💥 Error during analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python debug_device_detailed.py <device_id>")
        print("Example: python debug_device_detailed.py CE:50:AA:56:9C:69")
        sys.exit(1)
    
    device_id = sys.argv[1]
    asyncio.run(debug_device_detailed(device_id))