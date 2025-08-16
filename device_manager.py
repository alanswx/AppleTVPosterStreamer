import asyncio
import pyatv
from pyatv import connect, scan, pair
from pyatv.const import Protocol
from typing import List, Dict, Optional, Callable, Any
import logging
from datetime import datetime
from database import DatabaseManager
from config import config

class DeviceManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.discovered_devices: Dict[str, Dict] = {}
        self.connected_devices: Dict[str, Any] = {}
        self.authentication_callbacks: Dict[str, Callable] = {}
        self._active_pairings: Dict[str, Dict] = {}  # Track active pairing processes
        self.logger = logging.getLogger(__name__)
        
    async def scan_for_devices(self, timeout: int = None) -> List[Dict[str, Any]]:
        timeout = timeout or config.DEVICE_SCAN_TIMEOUT
        self.logger.info(f"Scanning for AirPlay devices (timeout: {timeout}s)")
        
        try:
            discovered = []
            devices = await scan(timeout=timeout, loop=asyncio.get_event_loop())
            
            for device in devices:
                # Filter for devices that support AirPlay
                airplay_service = device.get_service(Protocol.AirPlay)
                if not airplay_service:
                    continue
                    
                device_info = {
                    'device_id': device.identifier,
                    'name': device.name,
                    'address': str(device.address),
                    'port': airplay_service.port,
                    'device_type': 'AirPlay',
                    'protocol': 'AirPlay',
                    'services': [str(service) for service in device.services],
                    'is_active': False  # Newly discovered devices start as inactive
                }
                
                self.discovered_devices[device.identifier] = device_info
                discovered.append(device_info)
                
                # Save discovered device to database
                await self.db_manager.add_device(
                    device_id=device.identifier,
                    name=device.name,
                    address=str(device.address),
                    port=airplay_service.port,
                    device_type='AirPlay'
                )
                
            self.logger.info(f"Found {len(discovered)} AirPlay devices")
            return discovered
            
        except Exception as e:
            self.logger.error(f"Error scanning for devices: {e}")
            return []
    
    async def connect_to_device(self, device_id: str, credentials: str = None) -> bool:
        try:
            # Get device info from database or discovered devices
            device_info = await self.db_manager.get_device(device_id)
            if not device_info and device_id in self.discovered_devices:
                device_info = self.discovered_devices[device_id]
            
            if not device_info:
                self.logger.error(f"Device {device_id} not found")
                return False
            
            # Use stored credentials if available
            if device_info.get('credentials'):
                credentials = device_info['credentials']
            
            # Create connection config correctly
            device_config = pyatv.conf.AppleTV(device_info['address'], device_info['name'])
            
            # Add AirPlay service
            airplay_service = pyatv.conf.ManualService(
                device_id,  # identifier
                Protocol.AirPlay,
                device_info.get('port', 7000),
                {},  # properties
                credentials=credentials
            )
            device_config.add_service(airplay_service)
            
            self.logger.info(f"Attempting to connect to {device_info['name']} ({device_id})")
            
            # Connect with timeout
            connection = await asyncio.wait_for(
                connect(device_config, loop=asyncio.get_event_loop()),
                timeout=config.AIRPLAY_TIMEOUT
            )
            
            self.connected_devices[device_id] = {
                'connection': connection,
                'device_info': device_info,
                'connected_at': datetime.now(),
                'is_active': True
            }
            
            # Update database
            await self.db_manager.update_device_status(device_id, True, 0)
            
            self.logger.info(f"Successfully connected to {device_info['name']}")
            return True
            
        except asyncio.TimeoutError:
            self.logger.error(f"Connection timeout for device {device_id}")
            await self.db_manager.update_device_status(device_id, False)
            return False
        except Exception as e:
            self.logger.error(f"Failed to connect to device {device_id}: {e}")
            await self.db_manager.update_device_status(device_id, False)
            
            # Handle authentication required
            if ("authentication" in str(e).lower() or 
                "pin" in str(e).lower() or
                "pairing" in str(e).lower() or 
                "credentials" in str(e).lower()):
                self.logger.info(f"Device {device_id} requires authentication/pairing")
                if device_id in self.authentication_callbacks:
                    await self.authentication_callbacks[device_id](device_id, "Device requires pairing")
                return False
            
            return False
    
    async def start_pairing(self, device_id: str) -> Dict[str, Any]:
        """
        Initiate AirPlay pairing process.
        Returns pairing info including whether device provides PIN.
        """
        try:
            device_info = await self.db_manager.get_device(device_id)
            if not device_info and device_id in self.discovered_devices:
                device_info = self.discovered_devices[device_id]
            
            if not device_info:
                self.logger.error(f"Device {device_id} not found")
                return {'success': False, 'error': 'Device not found'}
            
            # Rescan to get proper device config with pairing requirements
            devices = await scan(identifier=device_id, timeout=5, loop=asyncio.get_event_loop())
            if not devices:
                return {'success': False, 'error': 'Device not found during scan'}
            
            device_config = devices[0]
            
            # Check if AirPlay service exists and supports pairing
            service = device_config.get_service(Protocol.AirPlay)
            if not service:
                return {'success': False, 'error': 'Device does not support AirPlay'}
            
            if service.pairing == pyatv.const.PairingRequirement.NotNeeded:
                return {'success': False, 'error': 'Pairing not required for this device'}
            elif service.pairing == pyatv.const.PairingRequirement.Unsupported:
                return {'success': False, 'error': 'Pairing not supported for this device'}
            elif service.pairing == pyatv.const.PairingRequirement.Disabled:
                return {'success': False, 'error': 'Pairing is disabled. Check AirPlay settings on device.'}
            
            # Start pairing process
            pairing = await pair(device_config, Protocol.AirPlay, loop=asyncio.get_event_loop())
            await pairing.begin()
            
            # Store pairing handler for later use
            self._active_pairings = getattr(self, '_active_pairings', {})
            self._active_pairings[device_id] = {
                'pairing': pairing,
                'device_config': device_config,
                'device_info': device_info
            }
            
            return {
                'success': True,
                'device_provides_pin': pairing.device_provides_pin,
                'device_name': device_info['name']
            }
            
        except Exception as e:
            self.logger.error(f"Failed to start pairing for device {device_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    async def complete_pairing(self, device_id: str, pin: str) -> bool:
        """
        Complete AirPlay pairing with PIN and establish connection.
        """
        try:
            # Get active pairing
            active_pairings = getattr(self, '_active_pairings', {})
            if device_id not in active_pairings:
                self.logger.error(f"No active pairing found for device {device_id}")
                return False
            
            pairing_info = active_pairings[device_id]
            pairing = pairing_info['pairing']
            device_config = pairing_info['device_config']
            device_info = pairing_info['device_info']
            
            # Validate PIN format
            if not pin or not pin.isdigit() or len(pin) != 4:
                self.logger.error(f"Invalid PIN format for device {device_id}")
                return False
            
            # Set PIN and finish pairing
            pairing.pin(int(pin))
            await pairing.finish()
            
            if pairing.has_paired:
                # Store credentials
                credentials = pairing.service.credentials
                await self.db_manager.update_device_credentials(device_id, credentials)
                
                # Update service with credentials
                airplay_service = device_config.get_service(Protocol.AirPlay)
                airplay_service.credentials = credentials
                
                # Connect with credentials
                connection = await asyncio.wait_for(
                    connect(device_config, loop=asyncio.get_event_loop()),
                    timeout=15  # 15 second timeout for initial connection
                )
                
                self.connected_devices[device_id] = {
                    'connection': connection,
                    'device_info': device_info,
                    'connected_at': datetime.now(),
                    'is_active': True
                }
                
                await self.db_manager.update_device_status(device_id, True, 0)
                
                # Cleanup
                await pairing.close()
                del active_pairings[device_id]
                
                self.logger.info(f"Successfully paired and connected to device {device_id}")
                return True
            else:
                await pairing.close()
                del active_pairings[device_id]
                self.logger.error(f"Pairing failed for device {device_id}")
                return False
            
        except pyatv.exceptions.PairingError as e:
            self.logger.error(f"Pairing error for device {device_id}: {e}")
            # Cleanup on failure
            active_pairings = getattr(self, '_active_pairings', {})
            if device_id in active_pairings:
                try:
                    await active_pairings[device_id]['pairing'].close()
                except:
                    pass
                del active_pairings[device_id]
            return False
        except asyncio.TimeoutError:
            self.logger.error(f"Connection timeout after pairing for device {device_id}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during pairing completion for device {device_id}: {e}")
            # Cleanup on failure
            active_pairings = getattr(self, '_active_pairings', {})
            if device_id in active_pairings:
                try:
                    await active_pairings[device_id]['pairing'].close()
                except:
                    pass
                del active_pairings[device_id]
            return False
    
    async def cancel_pairing(self, device_id: str) -> bool:
        """Cancel active pairing process."""
        try:
            active_pairings = getattr(self, '_active_pairings', {})
            if device_id in active_pairings:
                await active_pairings[device_id]['pairing'].close()
                del active_pairings[device_id]
                self.logger.info(f"Cancelled pairing for device {device_id}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error cancelling pairing for device {device_id}: {e}")
            return False
    
    async def authenticate_device(self, device_id: str, pin: str) -> bool:
        """
        Legacy method - now uses the new two-step pairing process.
        """
        self.logger.warning("authenticate_device is deprecated, use start_pairing + complete_pairing")
        
        # Start pairing
        pairing_result = await self.start_pairing(device_id)
        if not pairing_result['success']:
            return False
        
        # Complete pairing
        return await self.complete_pairing(device_id, pin)
    
    async def disconnect_device(self, device_id: str):
        if device_id in self.connected_devices:
            try:
                connection = self.connected_devices[device_id]['connection']
                connection.close()
                del self.connected_devices[device_id]
                await self.db_manager.update_device_status(device_id, False)
                self.logger.info(f"Disconnected from device {device_id}")
            except Exception as e:
                self.logger.error(f"Error disconnecting from device {device_id}: {e}")
    
    async def disconnect_all_devices(self):
        device_ids = list(self.connected_devices.keys())
        for device_id in device_ids:
            await self.disconnect_device(device_id)
    
    async def reconnect_device(self, device_id: str) -> bool:
        # Disconnect first if connected
        if device_id in self.connected_devices:
            await self.disconnect_device(device_id)
        
        # Attempt reconnection with retry logic
        for attempt in range(config.RECONNECT_ATTEMPTS):
            self.logger.info(f"Reconnection attempt {attempt + 1}/{config.RECONNECT_ATTEMPTS} for device {device_id}")
            
            if await self.connect_to_device(device_id):
                return True
            
            if attempt < config.RECONNECT_ATTEMPTS - 1:
                await asyncio.sleep(config.RECONNECT_DELAY)
        
        self.logger.error(f"Failed to reconnect to device {device_id} after {config.RECONNECT_ATTEMPTS} attempts")
        return False
    
    def register_authentication_callback(self, device_id: str, callback: Callable):
        self.authentication_callbacks[device_id] = callback
    
    def is_device_connected(self, device_id: str) -> bool:
        return device_id in self.connected_devices and self.connected_devices[device_id]['is_active']
    
    def get_connected_devices(self) -> List[str]:
        return [device_id for device_id in self.connected_devices 
                if self.connected_devices[device_id]['is_active']]
    
    def get_device_connection(self, device_id: str):
        if device_id in self.connected_devices:
            return self.connected_devices[device_id]['connection']
        return None
    
    async def health_check(self):
        """Check health of all connected devices and attempt reconnection if needed"""
        for device_id in list(self.connected_devices.keys()):
            try:
                connection = self.connected_devices[device_id]['connection']
                # Simple health check - could be improved with actual ping
                if not connection:
                    raise Exception("Connection is None")
                    
            except Exception as e:
                self.logger.warning(f"Device {device_id} appears disconnected: {e}")
                self.connected_devices[device_id]['is_active'] = False
                await self.db_manager.update_device_status(device_id, False)
                
                # Attempt reconnection in background
                asyncio.create_task(self.reconnect_device(device_id))
    
    async def get_device_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        # First check connected devices
        if device_id in self.connected_devices:
            device_data = self.connected_devices[device_id]['device_info'].copy()
            device_data['is_connected'] = True
            device_data['connected_at'] = self.connected_devices[device_id]['connected_at']
            return device_data
        
        # Then check database
        device_data = await self.db_manager.get_device(device_id)
        if device_data:
            device_data['is_connected'] = False
            return device_data
        
        # Finally check discovered devices
        if device_id in self.discovered_devices:
            device_data = self.discovered_devices[device_id].copy()
            device_data['is_connected'] = False
            return device_data
        
        return None