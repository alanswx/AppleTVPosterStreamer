import sqlite3
import aiosqlite
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from cryptography.fernet import Fernet
import base64
import os
from config import config

class DatabaseManager:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher = Fernet(self.encryption_key)
    
    def _get_or_create_encryption_key(self) -> bytes:
        key_file = '.encryption_key'
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            os.chmod(key_file, 0o600)  # Read/write for owner only
            return key
    
    def _encrypt_credentials(self, credentials: str) -> str:
        if not credentials:
            return ""
        return self.cipher.encrypt(credentials.encode()).decode()
    
    def _decrypt_credentials(self, encrypted_credentials: str) -> str:
        if not encrypted_credentials:
            return ""
        return self.cipher.decrypt(encrypted_credentials.encode()).decode()
    
    async def init_database(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    address TEXT NOT NULL,
                    port INTEGER,
                    device_type TEXT,
                    credentials TEXT,
                    last_connected TIMESTAMP,
                    is_active BOOLEAN DEFAULT 0,
                    connection_attempts INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS slideshow_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_name TEXT,
                    images_directory TEXT,
                    display_time INTEGER,
                    active_devices TEXT,
                    is_running BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_device_id ON devices(device_id);
            ''')
            
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_is_active ON devices(is_active);
            ''')
            
            await db.commit()
    
    async def add_device(self, device_id: str, name: str, address: str, 
                        port: int = None, device_type: str = None, 
                        credentials: str = None) -> bool:
        try:
            encrypted_creds = self._encrypt_credentials(credentials) if credentials else ""
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT OR REPLACE INTO devices 
                    (device_id, name, address, port, device_type, credentials, last_connected)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (device_id, name, address, port, device_type, encrypted_creds, datetime.now()))
                await db.commit()
                return True
        except Exception as e:
            print(f"Error adding device: {e}")
            return False
    
    async def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT device_id, name, address, port, device_type, credentials, 
                       last_connected, is_active, connection_attempts
                FROM devices WHERE device_id = ?
            ''', (device_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    device_data = {
                        'device_id': row[0],
                        'name': row[1],
                        'address': row[2],
                        'port': row[3],
                        'device_type': row[4],
                        'credentials': self._decrypt_credentials(row[5]) if row[5] else None,
                        'last_connected': row[6],
                        'is_active': bool(row[7]),
                        'connection_attempts': row[8]
                    }
                    return device_data
                return None
    
    async def get_all_devices(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT device_id, name, address, port, device_type, 
                       last_connected, is_active, connection_attempts
                FROM devices ORDER BY name
            ''') as cursor:
                rows = await cursor.fetchall()
                devices = []
                for row in rows:
                    devices.append({
                        'device_id': row[0],
                        'name': row[1],
                        'address': row[2],
                        'port': row[3],
                        'device_type': row[4],
                        'last_connected': row[5],
                        'is_active': bool(row[6]),
                        'connection_attempts': row[7]
                    })
                return devices
    
    async def update_device_status(self, device_id: str, is_active: bool, 
                                 connection_attempts: int = None):
        async with aiosqlite.connect(self.db_path) as db:
            if connection_attempts is not None:
                await db.execute('''
                    UPDATE devices 
                    SET is_active = ?, connection_attempts = ?, last_connected = ?
                    WHERE device_id = ?
                ''', (is_active, connection_attempts, datetime.now(), device_id))
            else:
                await db.execute('''
                    UPDATE devices 
                    SET is_active = ?, last_connected = ?
                    WHERE device_id = ?
                ''', (is_active, datetime.now(), device_id))
            await db.commit()
    
    async def update_device_credentials(self, device_id: str, credentials: str):
        encrypted_creds = self._encrypt_credentials(credentials)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE devices SET credentials = ? WHERE device_id = ?
            ''', (encrypted_creds, device_id))
            await db.commit()
    
    async def remove_device(self, device_id: str) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('DELETE FROM devices WHERE device_id = ?', (device_id,))
                await db.commit()
                return True
        except Exception as e:
            print(f"Error removing device: {e}")
            return False
    
    async def save_slideshow_session(self, session_name: str, images_directory: str,
                                   display_time: int, active_devices: List[str]):
        active_devices_str = ','.join(active_devices)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO slideshow_sessions
                (session_name, images_directory, display_time, active_devices, last_updated)
                VALUES (?, ?, ?, ?, ?)
            ''', (session_name, images_directory, display_time, active_devices_str, datetime.now()))
            await db.commit()
    
    async def get_last_slideshow_session(self) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT session_name, images_directory, display_time, active_devices
                FROM slideshow_sessions 
                ORDER BY last_updated DESC LIMIT 1
            ''') as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        'session_name': row[0],
                        'images_directory': row[1],
                        'display_time': row[2],
                        'active_devices': row[3].split(',') if row[3] else []
                    }
                return None