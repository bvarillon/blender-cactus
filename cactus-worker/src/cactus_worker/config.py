"""Configuration for the Cactus worker."""

import socket
import platform
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class WorkerConfig(BaseSettings):
    """Worker configuration settings."""
    
    # Server connection
    server_host: str = Field(default="localhost", description="Server host address")
    server_port: int = Field(default=8000, description="Server port")
    server_websocket_path: str = Field(default="/ws", description="Server WebSocket path")
    
    # Worker identity
    worker_name: Optional[str] = Field(default=None, description="Worker name (auto-generated if not set)")
    worker_id: Optional[str] = Field(default=None, description="Worker ID (auto-generated if not set)")
    
    # Blender settings
    blender_path: str = Field(default="blender", description="Path to Blender executable")
    blender_version: str = Field(default="3.6.0", description="Blender version")
    
    # Render settings
    temp_dir: str = Field(default="/tmp/cactus", description="Temporary directory for render files")
    output_dir: str = Field(default="/output/cactus", description="Output directory for rendered frames")
    
    # System detection
    auto_detect_gpu: bool = Field(default=True, description="Auto-detect GPU information")
    auto_detect_cpu: bool = Field(default=True, description="Auto-detect CPU information")
    
    # Connection settings
    reconnect_interval: int = Field(default=5, description="Seconds to wait before reconnecting")
    ping_interval: int = Field(default=30, description="Seconds between ping messages")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
    
    def get_worker_name(self) -> str:
        """Get the worker name, auto-generating if not set."""
        if self.worker_name:
            return self.worker_name
        return f"{platform.node()}-worker"
    
    def get_hostname(self) -> str:
        """Get the hostname."""
        return socket.gethostname()
    
    def get_cpu_cores(self) -> int:
        """Get the number of CPU cores."""
        import os
        return os.cpu_count() or 1
    
    def get_memory_gb(self) -> float:
        """Get available memory in GB."""
        try:
            import psutil
            return psutil.virtual_memory().total / (1024 ** 3)
        except ImportError:
            # Fallback: try to read from /proc/meminfo on Linux
            try:
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            return float(line.split()[1]) / (1024 ** 2)  # Convert KB to GB
            except:
                pass
            return 8.0  # Default fallback
    
    def get_gpu_info(self) -> tuple:
        """Get GPU information (count, models)."""
        if not self.auto_detect_gpu:
            return 0, []
        
        try:
            import pynvml
            pynvml.nvmlInit()
            handle_count = pynvml.nvmlDeviceGetCount()
            models = []
            for i in range(handle_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle)
                models.append(name.decode("utf-8"))
            pynvml.nvmlShutdown()
            return handle_count, models
        except ImportError:
            pass
        
        # Try alternative methods
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                gpus = [g.strip() for g in result.stdout.strip().split("\n") if g.strip()]
                return len(gpus), gpus
        except:
            pass
        
        return 0, []


# Global config instance
config = WorkerConfig()
