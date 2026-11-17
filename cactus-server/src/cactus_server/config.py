"""Configuration for the Cactus server."""

from pydantic_settings import BaseSettings
from pydantic import Field


class ServerConfig(BaseSettings):
    """Server configuration settings."""
    
    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host address")
    port: int = Field(default=8000, description="Server port")
    server_name: str = Field(default="Cactus Server", description="Server name")
    server_version: str = Field(default="0.1.0", description="Server version")
    
    # WebSocket settings
    websocket_path: str = Field(default="/ws", description="WebSocket endpoint path")
    websocket_ping_interval: int = Field(default=30, description="WebSocket ping interval in seconds")
    websocket_ping_timeout: int = Field(default=60, description="WebSocket ping timeout in seconds")
    
    # Worker settings
    max_workers: int = Field(default=100, description="Maximum number of workers")
    worker_timeout: int = Field(default=300, description="Worker timeout in seconds")
    
    # Task settings
    max_queue_size: int = Field(default=1000, description="Maximum task queue size")
    task_timeout: int = Field(default=3600, description="Task timeout in seconds")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Global config instance
config = ServerConfig()
