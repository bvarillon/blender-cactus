"""WebSocket server for Blender Cactus render farm."""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

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

from cactus_server.config import ServerConfig, config
from cactus_server.worker_manager import WorkerManager
from cactus_server.task_queue import TaskQueue

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_types: Dict[str, str] = {}  # connection_id -> type (worker/client)
        self.connection_lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, connection_type: str = "unknown") -> str:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        connection_id = str(uuid.uuid4())
        
        async with self.connection_lock:
            self.active_connections[connection_id] = websocket
            self.connection_types[connection_id] = connection_type
        
        logger.info(f"New {connection_type} connection: {connection_id}")
        return connection_id
    
    async def disconnect(self, connection_id: str) -> None:
        """Remove a WebSocket connection."""
        async with self.connection_lock:
            if connection_id in self.active_connections:
                await self.active_connections[connection_id].close()
                del self.active_connections[connection_id]
                del self.connection_types[connection_id]
        
        logger.info(f"Connection closed: {connection_id}")
    
    async def send_message(self, connection_id: str, message: BaseMessage) -> bool:
        """Send a message to a specific connection."""
        async with self.connection_lock:
            if connection_id not in self.active_connections:
                return False
            
            websocket = self.active_connections[connection_id]
        
        try:
            await websocket.send_text(message.model_dump_json())
            return True
        except Exception as e:
            logger.error(f"Failed to send message to {connection_id}: {e}")
            await self.disconnect(connection_id)
            return False
    
    async def broadcast_message(self, message: BaseMessage, exclude_connection: Optional[str] = None) -> int:
        """Broadcast a message to all connections."""
        sent_count = 0
        
        async with self.connection_lock:
            connections = list(self.active_connections.items())
        
        for connection_id, websocket in connections:
            if connection_id == exclude_connection:
                continue
            
            try:
                await websocket.send_text(message.model_dump_json())
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to broadcast to {connection_id}: {e}")
                await self.disconnect(connection_id)
        
        return sent_count
    
    async def broadcast_to_clients(self, message: BaseMessage) -> int:
        """Broadcast a message to all client connections."""
        sent_count = 0
        
        async with self.connection_lock:
            connections = list(self.active_connections.items())
        
        for connection_id, websocket in connections:
            if self.connection_types.get(connection_id) != "client":
                continue
            
            try:
                await websocket.send_text(message.model_dump_json())
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to broadcast to client {connection_id}: {e}")
                await self.disconnect(connection_id)
        
        return sent_count


class CactusServer:
    """Main server class for Blender Cactus render farm."""
    
    def __init__(
        self,
        server_config: Optional[ServerConfig] = None,
        worker_manager: Optional[WorkerManager] = None,
        task_queue: Optional[TaskQueue] = None,
    ):
        self.config = server_config or config
        self.worker_manager = worker_manager or WorkerManager(
            max_workers=self.config.max_workers,
            worker_timeout=self.config.worker_timeout,
        )
        self.task_queue = task_queue or TaskQueue(max_queue_size=self.config.max_queue_size)
        self.connection_manager = ConnectionManager()
        
        # Track worker connections by worker_id
        self.worker_connections: Dict[UUID, str] = {}  # worker_id -> connection_id
        
        # Setup logging
        logging.basicConfig(
            level=self.config.log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        
        # Create FastAPI app
        self.app = FastAPI(title=self.config.server_name, version=self.config.server_version)
        
        # Setup routes
        self._setup_routes()
    
    def _setup_routes(self) -> None:
        """Setup WebSocket and HTTP routes."""
        
        @self.app.websocket(self.config.websocket_path)
        async def websocket_endpoint(websocket: WebSocket):
            connection_id = await self.connection_manager.connect(websocket, "unknown")
            connection_type = "unknown"
            worker_id: Optional[UUID] = None
            
            try:
                while True:
                    data = await websocket.receive_text()
                    
                    try:
                        message = self._parse_message(data)
                    except Exception as e:
                        logger.error(f"Failed to parse message from {connection_id}: {e}")
                        error_msg = ServerErrorMessage(
                            message_type=MessageType.SERVER_ERROR,
                            error_code="INVALID_MESSAGE",
                            error_message=f"Failed to parse message: {str(e)}",
                        )
                        await websocket.send_text(error_msg.model_dump_json())
                        continue
                    
                    # Handle different message types
                    if message.message_type == MessageType.WORKER_REGISTER:
                        worker_msg = self._parse_message(data, WorkerRegisterMessage)
                        await self._handle_worker_register(websocket, connection_id, worker_msg)
                        connection_type = "worker"
                        worker_id = worker_msg.worker_info.worker_id
                        self.worker_connections[worker_id] = connection_id
                        
                    elif message.message_type == MessageType.WORKER_STATUS:
                        status_msg = self._parse_message(data, WorkerStatusMessage)
                        await self._handle_worker_status(status_msg)
                        
                    elif message.message_type == MessageType.WORKER_DEREGISTER:
                        dereg_msg = self._parse_message(data, WorkerDeregisterMessage)
                        await self._handle_worker_deregister(dereg_msg)
                        
                    elif message.message_type == MessageType.TASK_RESULT:
                        result_msg = self._parse_message(data, TaskResultMessage)
                        await self._handle_task_result(result_msg)
                        
                    elif message.message_type == MessageType.CLIENT_SUBMIT:
                        submit_msg = self._parse_message(data, ClientSubmitMessage)
                        await self._handle_client_submit(submit_msg)
                        connection_type = "client"
                        
                    elif message.message_type == MessageType.CLIENT_CANCEL:
                        cancel_msg = self._parse_message(data, ClientCancelMessage)
                        await self._handle_client_cancel(cancel_msg)
                        
                    else:
                        logger.warning(f"Unknown message type: {message.message_type}")
                        error_msg = ServerErrorMessage(
                            message_type=MessageType.SERVER_ERROR,
                            error_code="UNKNOWN_MESSAGE_TYPE",
                            error_message=f"Unknown message type: {message.message_type}",
                        )
                        await websocket.send_text(error_msg.model_dump_json())
                    
                    # Update connection type
                    if connection_id in self.connection_manager.connection_types:
                        self.connection_manager.connection_types[connection_id] = connection_type
                    
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {connection_id}")
                if worker_id and worker_id in self.worker_connections:
                    await self.worker_manager.deregister_worker(worker_id, reason="disconnected")
                    del self.worker_connections[worker_id]
                await self.connection_manager.disconnect(connection_id)
            except Exception as e:
                logger.error(f"Error in WebSocket connection {connection_id}: {e}")
                if worker_id and worker_id in self.worker_connections:
                    await self.worker_manager.deregister_worker(worker_id, reason="error")
                    del self.worker_connections[worker_id]
                await self.connection_manager.disconnect(connection_id)
        
        @self.app.get("/")
        async def root():
            return {
                "server": self.config.server_name,
                "version": self.config.server_version,
                "workers": self.worker_manager.get_worker_count(),
                "tasks": self.task_queue.get_total_tasks(),
            }
        
        @self.app.get("/status")
        async def status():
            return {
                "server": self.config.server_name,
                "version": self.config.server_version,
                "workers": {
                    "total": self.worker_manager.get_worker_count(),
                    "idle": len(self.worker_manager.get_idle_workers()),
                    "processing": len(self.worker_manager.get_processing_workers()),
                },
                "tasks": self.task_queue.get_task_counts_by_status(),
                "queue_size": self.task_queue.get_queue_size(),
            }
    
    def _parse_message(self, data: str, message_class: type = BaseMessage) -> BaseMessage:
        """Parse a message from JSON data."""
        json_data = json.loads(data)
        return message_class(**json_data)
    
    async def _handle_worker_register(
        self, websocket: WebSocket, connection_id: str, message: WorkerRegisterMessage
    ) -> None:
        """Handle worker registration."""
        worker_info = message.worker_info
        
        # Register worker
        success = await self.worker_manager.register_worker(
            worker_info.worker_id, websocket, worker_info
        )
        
        if success:
            # Send acknowledgment
            ack = ServerAckMessage(
                message_type=MessageType.SERVER_ACK,
                in_response_to=message.message_id,
                success=True,
                message="Worker registered successfully",
            )
            await websocket.send_text(ack.model_dump_json())
            
            # Send server config
            config_msg = ServerConfigMessage(
                message_type=MessageType.SERVER_CONFIG,
                server_name=self.config.server_name,
                server_version=self.config.server_version,
                max_workers=self.config.max_workers,
                queue_size=self.task_queue.get_queue_size(),
                active_tasks=len(self.task_queue.get_processing_tasks()),
            )
            await websocket.send_text(config_msg.model_dump_json())
            
            logger.info(f"Worker {worker_info.worker_id} registered: {worker_info.name}")
            
            # Try to assign a task if available
            await self._assign_tasks_to_idle_workers()
            
            # Broadcast status update
            await self._broadcast_status()
            
        else:
            error = ServerErrorMessage(
                message_type=MessageType.SERVER_ERROR,
                error_code="REGISTRATION_FAILED",
                error_message="Failed to register worker",
                in_response_to=message.message_id,
            )
            await websocket.send_text(error.model_dump_json())
    
    async def _handle_worker_status(self, message: WorkerStatusMessage) -> None:
        """Handle worker status update."""
        await self.worker_manager.update_worker_status(
            message.worker_id, message.status, message.current_task_id
        )
        
        logger.debug(f"Worker {message.worker_id} status: {message.status}")
        
        # If worker is idle, try to assign a new task
        if message.status == "idle":
            await self._assign_tasks_to_idle_workers()
        
        # Broadcast status update
        await self._broadcast_status()
    
    async def _handle_worker_deregister(self, message: WorkerDeregisterMessage) -> None:
        """Handle worker deregistration."""
        await self.worker_manager.deregister_worker(message.worker_id, message.reason)
        
        if message.worker_id in self.worker_connections:
            connection_id = self.worker_connections[message.worker_id]
            await self.connection_manager.disconnect(connection_id)
            del self.worker_connections[message.worker_id]
        
        logger.info(f"Worker {message.worker_id} deregistered: {message.reason}")
        
        # Broadcast status update
        await self._broadcast_status()
    
    async def _handle_task_result(self, message: TaskResultMessage) -> None:
        """Handle task result from a worker."""
        task = self.task_queue.get_task(message.task_id)
        
        if not task:
            logger.warning(f"Received result for unknown task: {message.task_id}")
            return
        
        # Update task status
        if message.status == TaskStatus.COMPLETED:
            await self.task_queue.complete_task(
                message.task_id,
                output_file=message.output_file,
                render_time=message.render_time_seconds,
            )
            await self.worker_manager.update_worker_status(message.worker_id, "idle")
        else:
            await self.task_queue.fail_task(message.task_id, message.error_message or "Unknown error")
            await self.worker_manager.update_worker_status(message.worker_id, "idle")
        
        logger.info(f"Task {message.task_id} completed with status: {message.status}")
        
        # Assign new tasks to idle workers
        await self._assign_tasks_to_idle_workers()
        
        # Broadcast status update
        await self._broadcast_status()
    
    async def _handle_client_submit(self, message: ClientSubmitMessage) -> None:
        """Handle client project submission."""
        project_info = message.project_info
        
        # Create tasks for all frames
        tasks = []
        frame_start = project_info.frame_start
        frame_end = project_info.frame_end
        frame_step = project_info.frame_step
        
        for frame in range(frame_start, frame_end + 1, frame_step):
            task = RenderTask(
                task_id=UUID(int=0),
                project_id=project_info.project_id,
                frame_number=frame,
                status=TaskStatus.PENDING,
            )
            # Generate proper UUID
            task.task_id = UUID(int=0)
            tasks.append(task)
        
        # Add tasks to queue
        for task in tasks:
            await self.task_queue.add_task(task)
        
        logger.info(f"Client submitted project {project_info.project_id} with {len(tasks)} tasks")
        
        # Send acknowledgment
        ack = ServerAckMessage(
            message_type=MessageType.SERVER_ACK,
            in_response_to=message.message_id,
            success=True,
            message=f"Project {project_info.project_id} submitted with {len(tasks)} tasks",
        )
        
        # Send to client
        await self.connection_manager.broadcast_to_clients(ack.model_dump_json())
        
        # Try to assign tasks
        await self._assign_tasks_to_idle_workers()
        
        # Broadcast status update
        await self._broadcast_status()
    
    async def _handle_client_cancel(self, message: ClientCancelMessage) -> None:
        """Handle client project cancellation."""
        cancelled_count = await self.task_queue.cancel_project_tasks(message.project_id)
        
        logger.info(f"Client cancelled project {message.project_id}, {cancelled_count} tasks cancelled")
        
        # Send acknowledgment
        ack = ServerAckMessage(
            message_type=MessageType.SERVER_ACK,
            in_response_to=message.message_id,
            success=True,
            message=f"Cancelled {cancelled_count} tasks for project {message.project_id}",
        )
        
        await self.connection_manager.broadcast_to_clients(ack.model_dump_json())
        
        # Broadcast status update
        await self._broadcast_status()
    
    async def _assign_tasks_to_idle_workers(self) -> int:
        """Assign tasks to all idle workers."""
        assigned_count = 0
        idle_workers = self.worker_manager.get_idle_workers()
        
        for worker in idle_workers:
            task = await self.task_queue.get_next_task()
            if not task:
                break
            
            # Assign task to worker
            await self.task_queue.assign_task(task.task_id, worker.worker_id)
            
            # Get project info
            project_info = None
            project_tasks = self.task_queue.get_tasks_by_project(task.project_id)
            if project_tasks:
                # This is a simplified approach - in reality we'd need to store project info
                pass
            
            # Create assignment message
            assignment = TaskAssignmentMessage(
                message_type=MessageType.TASK_ASSIGNMENT,
                task=task,
                project_info=ProjectInfo(
                    project_id=task.project_id,
                    project_name=f"Project_{task.project_id}",
                    blender_file_path="/tmp/test.blend",
                    output_path="/tmp/output",
                ),
            )
            
            # Send to worker
            connection_id = self.worker_connections.get(worker.worker_id)
            if connection_id:
                await self.connection_manager.send_message(connection_id, assignment)
                await self.worker_manager.update_worker_status(worker.worker_id, "processing", task.task_id)
                assigned_count += 1
        
        if assigned_count > 0:
            logger.info(f"Assigned {assigned_count} tasks to idle workers")
        
        return assigned_count
    
    async def _broadcast_status(self) -> None:
        """Broadcast system status to all clients."""
        status = BroadcastStatusMessage(
            message_type=MessageType.BROADCAST_STATUS,
            total_workers=self.worker_manager.get_worker_count(),
            active_workers=len(self.worker_manager.get_processing_workers()),
            pending_tasks=len(self.task_queue.get_pending_tasks()),
            processing_tasks=len(self.task_queue.get_processing_tasks()),
            completed_tasks=len(self.task_queue.get_completed_tasks()),
            worker_summaries=self.worker_manager.get_all_workers_summary(),
        )
        
        await self.connection_manager.broadcast_to_clients(status)
    
    async def run(self) -> None:
        """Run the server."""
        import uvicorn
        
        logger.info(f"Starting {self.config.server_name} v{self.config.server_version}")
        logger.info(f"Listening on {self.config.host}:{self.config.port}")
        
        await uvicorn.run(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level=self.config.log_level.lower(),
        )


def create_server() -> CactusServer:
    """Create and return a new CactusServer instance."""
    return CactusServer()


if __name__ == "__main__":
    import asyncio
    
    server = create_server()
    asyncio.run(server.run())
