import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    # Flask settings
    FLASK_HOST: str = "0.0.0.0"
    FLASK_PORT: int = 8080  # Avoid 5000 (AirPlay conflict)
    SECRET_KEY: str = "your-secret-key-change-this"
    DEBUG: bool = True
    
    # Slideshow settings
    DEFAULT_DISPLAY_TIME: int = 5  # seconds
    MAX_DISPLAYS: int = 16
    SUPPORTED_IMAGE_FORMATS: tuple = ('.jpg', '.jpeg', '.png', '.gif')
    
    # Image settings
    MAX_IMAGE_SIZE: tuple = (3840, 2160)  # 4K resolution
    IMAGE_QUALITY: int = 85  # JPEG quality
    
    # Database settings
    DATABASE_PATH: str = "devices.db"
    
    # AirPlay settings
    AIRPLAY_TIMEOUT: int = 10  # seconds
    DEVICE_SCAN_TIMEOUT: int = 5  # seconds
    RECONNECT_ATTEMPTS: int = 3
    RECONNECT_DELAY: int = 2  # seconds
    
    # Directory settings
    DEFAULT_IMAGES_DIR: str = "./images"
    
    @classmethod
    def from_env(cls) -> 'Config':
        return cls(
            FLASK_HOST=os.getenv('FLASK_HOST', cls.FLASK_HOST),
            FLASK_PORT=int(os.getenv('FLASK_PORT', cls.FLASK_PORT)),
            SECRET_KEY=os.getenv('SECRET_KEY', cls.SECRET_KEY),
            DEBUG=os.getenv('DEBUG', 'True').lower() == 'true',
            DEFAULT_DISPLAY_TIME=int(os.getenv('DEFAULT_DISPLAY_TIME', cls.DEFAULT_DISPLAY_TIME)),
            MAX_DISPLAYS=int(os.getenv('MAX_DISPLAYS', cls.MAX_DISPLAYS)),
            MAX_IMAGE_SIZE=tuple(map(int, os.getenv('MAX_IMAGE_SIZE', '3840,2160').split(','))),
            IMAGE_QUALITY=int(os.getenv('IMAGE_QUALITY', cls.IMAGE_QUALITY)),
            DATABASE_PATH=os.getenv('DATABASE_PATH', cls.DATABASE_PATH),
            AIRPLAY_TIMEOUT=int(os.getenv('AIRPLAY_TIMEOUT', cls.AIRPLAY_TIMEOUT)),
            DEVICE_SCAN_TIMEOUT=int(os.getenv('DEVICE_SCAN_TIMEOUT', cls.DEVICE_SCAN_TIMEOUT)),
            RECONNECT_ATTEMPTS=int(os.getenv('RECONNECT_ATTEMPTS', cls.RECONNECT_ATTEMPTS)),
            RECONNECT_DELAY=int(os.getenv('RECONNECT_DELAY', cls.RECONNECT_DELAY)),
            DEFAULT_IMAGES_DIR=os.getenv('DEFAULT_IMAGES_DIR', cls.DEFAULT_IMAGES_DIR)
        )

config = Config.from_env()