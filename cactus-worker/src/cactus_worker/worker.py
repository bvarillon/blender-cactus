"""Worker for Blender Cactus render farm."""

import asyncio
import json
import logging
import platform
import socket
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

import websockets

from cactus_tools.schemas import (
    MessageType,
    BaseMessage,
    WorkerRegisterMessage,
    WorkerStatusMessage,
    WorkerDeregisterMessage,
    TaskAssignmentMessage,
    TaskResultMessage,
    TaskStatusMessage,
    ClientSubmitMessage,
    ClientCancelMessage,
    ServerConfigMessage,
    ServerAckMessage,
    ServerErrorMessage,
    BroadcastStatusMessage,
    WorkerInfo,
    ProjectInfo,
    RenderTask,
    TaskStatus,
    create_message,
)

from cactus_worker.config import WorkerConfig, config
from cactus_worker.blender_renderer import BlenderRenderer

logger = logging.getLogger(__name__)


class CactusWorker:
    """Worker that connects to the Cactus server and processes render tasks."""
    
    def __init__(
        self,
        worker_config: Optional[WorkerConfig] = None,
        blender_renderer: Optional[BlenderRenderer] = None,
    ):
        self.config = worker_config or config
        self.renderer = blender_renderer or BlenderRenderer(
            blender_path=self.config.blender_path,
            temp_dir=self.config.temp_dir,
            output_dir=self.config.output_dir,
        )
        
        # Worker identity
        self.worker_id = UUID(self.config.worker_id) if self.config.worker_id else UUID(int=0)
        self.worker_name = self.config.get_worker_name()
        self.hostname = self.config.get_hostname()
        
        # Worker info
        self.worker_info = self._create_worker_info()
        
        # Connection state
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self.server_url: str = f"ws://{self.config.server_host}:{self.config.server_port}{self.config.server_websocket_path}"
        
        # Current task
        self.current_task: Optional[RenderTask] = None
        self.current_project: Optional[ProjectInfo] = None
        self.is_rendering = False
        
        # Statistics
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.total_render_time = 0.0
        
        # Setup logging
        logging.basicConfig(
            level=self.config.log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
    
    def _create_worker_info(self) -> WorkerInfo:
        """Create worker information."""
        cpu_cores = self.config.get_cpu_cores()
        memory_gb = self.config.get_memory_gb()
        gpu_count, gpu_models = self.config.get_gpu_info()
        
        # Generate worker ID if not set
        if self.worker_id == UUID(int=0):
            self.worker_id = UUID(int=uuid.getnode() * 1000 + os.getpid())
        
        blender_version = self.renderer.get_blender_version() or self.config.blender_version
        
        return WorkerInfo(
            worker_id=self.worker_id,
            name=self.worker_name,
            hostname=self.hostname,
            cpu_cores=cpu_cores,
            gpu_count=gpu_count,
            gpu_models=gpu_models,
            memory_gb=round(memory_gb, 2),
            blender_version=blender_version,
            status="idle",
        )
    
    async def connect(self) -> bool:
        """Connect to the server."""
        try:
            logger.info(f"Connecting to server at {self.server_url}")
            
            self.websocket = await websockets.connect(
                self.server_url,
                ping_interval=self.config.ping_interval,
                ping_timeout=self.config.ping_interval * 2,
            )
            
            self.connected = True
            logger.info(f"Connected to server")
            
            # Register with server
            await self._register()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            self.connected = False
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from the server."""
        if not self.connected:
            return
        
        try:
            # Send deregister message
            deregister = WorkerDeregisterMessage(
                message_type=MessageType.WORKER_DEREGISTER,
                worker_id=self.worker_id,
                reason="shutdown",
            )
            await self._send_message(deregister)
        except Exception as e:
            logger.error(f"Error sending deregister message: {e}")
        
        try:
            if self.websocket:
                await self.websocket.close()
        except Exception as e:
            logger.error(f"Error closing WebSocket: {e}")
        
        self.connected = False
        self.websocket = None
        logger.info("Disconnected from server")
    
    async def _register(self) -> None:
        """Register with the server."""
        register_msg = WorkerRegisterMessage(
            message_type=MessageType.WORKER_REGISTER,
            worker_info=self.worker_info,
        )
        
        await self._send_message(register_msg)
        logger.info(f"Registered with server as worker {self.worker_id}")
    
    async def _send_message(self, message: BaseMessage) -> bool:
        """Send a message to the server."""
        if not self.connected or not self.websocket:
            logger.warning("Cannot send message: not connected")
            return False
        
        try:
            await self.websocket.send(message.model_dump_json())
            logger.debug(f"Sent message: {message.message_type}")
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            self.connected = False
            return False
    
    async def _send_status(self, status: str, progress: Optional[float] = None) -> None:
        """Send worker status update."""
        status_msg = WorkerStatusMessage(
            message_type=MessageType.WORKER_STATUS,
            worker_id=self.worker_id,
            status=status,
            current_task_id=self.current_task.task_id if self.current_task else None,
            progress_percent=progress,
        )
        await self._send_message(status_msg)
    
    async def _handle_message(self, data: str) -> None:
        """Handle a message from the server."""
        try:
            json_data = json.loads(data)
            message_type = json_data.get("message_type")
            
            if message_type == MessageType.TASK_ASSIGNMENT:
                await self._handle_task_assignment(json_data)
            elif message_type == MessageType.SERVER_CONFIG:
                self._handle_server_config(json_data)
            elif message_type == MessageType.SERVER_ACK:
                self._handle_server_ack(json_data)
            elif message_type == MessageType.SERVER_ERROR:
                self._handle_server_error(json_data)
            elif message_type == MessageType.BROADCAST_STATUS:
                self._handle_broadcast_status(json_data)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def _handle_task_assignment(self, json_data: Dict) -> None:
        """Handle a task assignment from the server."""
        message = TaskAssignmentMessage(**json_data)
        
        logger.info(f"Received task assignment: {message.task.task_id}, frame {message.task.frame_number}")
        
        self.current_task = message.task
        self.current_project = message.project_info
        self.is_rendering = True
        
        # Send status update
        await self._send_status("processing", progress=0.0)
        
        # Process the task
        asyncio.create_task(self._process_task())
    
    async def _process_task(self) -> None:
        """Process the current task."""
        if not self.current_task or not self.current_project:
            logger.warning("No task to process")
            self.is_rendering = False
            await self._send_status("idle")
            return
        
        task = self.current_task
        project = self.current_project
        
        try:
            logger.info(f"Starting render for task {task.task_id}, frame {task.frame_number}")
            
            # Update task status
            task.status = TaskStatus.PROCESSING
            await self._send_status("processing", progress=0.0)
            
            # Render the frame
            result = await self.renderer.render_task(task, project)
            
            # Send result
            result_msg = TaskResultMessage(
                message_type=MessageType.TASK_RESULT,
                task_id=task.task_id,
                worker_id=self.worker_id,
                status=result["status"],
                output_file=result.get("output_file"),
                render_time_seconds=result.get("render_time_seconds"),
                error_message=result.get("error_message"),
                frame_number=result.get("frame_number", task.frame_number),
            )
            
            await self._send_message(result_msg)
            
            # Update statistics
            if result["status"] == TaskStatus.COMPLETED:
                self.tasks_completed += 1
                self.total_render_time += result.get("render_time_seconds", 0)
            else:
                self.tasks_failed += 1
            
            logger.info(f"Task {task.task_id} completed with status: {result['status']}")
            
        except Exception as e:
            logger.error(f"Error processing task {task.task_id}: {e}")
            
            result_msg = TaskResultMessage(
                message_type=MessageType.TASK_RESULT,
                task_id=task.task_id,
                worker_id=self.worker_id,
                status=TaskStatus.FAILED,
                error_message=str(e),
                frame_number=task.frame_number,
            )
            
            await self._send_message(result_msg)
            self.tasks_failed += 1
            
        finally:
            self.current_task = None
            self.current_project = None
            self.is_rendering = False
            await self._send_status("idle")
    
    def _handle_server_config(self, json_data: Dict) -> None:
        """Handle server configuration message."""
        message = ServerConfigMessage(**json_data)
        logger.info(f"Server config: {message.server_name} v{message.server_version}")
        logger.info(f"Max workers: {message.max_workers}, Queue size: {message.queue_size}")
    
    def _handle_server_ack(self, json_data: Dict) -> None:
        """Handle server acknowledgment message."""
        message = ServerAckMessage(**json_data)
        if message.success:
            logger.debug(f"Server ACK: {message.message}")
        else:
            logger.warning(f"Server ACK (failure): {message.message}")
    
    def _handle_server_error(self, json_data: Dict) -> None:
        """Handle server error message."""
        message = ServerErrorMessage(**json_data)
        logger.error(f"Server error: {message.error_code} - {message.error_message}")
    
    def _handle_broadcast_status(self, json_data: Dict) -> None:
        """Handle broadcast status message."""
        message = BroadcastStatusMessage(**json_data)
        logger.debug(f"System status: {message.total_workers} workers, {message.pending_tasks} pending tasks")
    
    async def run(self) -> None:
        """Run the worker main loop."""
        while True:
            try:
                # Connect to server
                if not await self.connect():
                    logger.warning(f"Failed to connect, retrying in {self.config.reconnect_interval} seconds...")
                    await asyncio.sleep(self.config.reconnect_interval)
                    continue
                
                # Main message loop
                while self.connected:
                    try:
                        data = await self.websocket.recv()
                        await self._handle_message(data)
                    except websockets.ConnectionClosed:
                        logger.info("Connection closed by server")
                        self.connected = False
                        break
                    except Exception as e:
                        logger.error(f"Error receiving message: {e}")
                        self.connected = False
                        break
                
                # Disconnect and cleanup
                await self.disconnect()
                
                # Wait before reconnecting
                logger.warning(f"Disconnected, retrying in {self.config.reconnect_interval} seconds...")
                await asyncio.sleep(self.config.reconnect_interval)
                
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                await self.disconnect()
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                await asyncio.sleep(self.config.reconnect_interval)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics."""
        return {
            "worker_id": self.worker_id,
            "worker_name": self.worker_name,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "total_render_time": self.total_render_time,
            "connected": self.connected,
            "current_task_id": self.current_task.task_id if self.current_task else None,
            "is_rendering": self.is_rendering,
        }


def create_worker() -> CactusWorker:
    """Create and return a new CactusWorker instance."""
    return CactusWorker()


async def main():
    """Main entry point for the worker."""
    worker = create_worker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
