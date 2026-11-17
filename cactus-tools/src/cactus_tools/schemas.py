"""Pydantic schemas for WebSocket communication in Blender Cactus render farm."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class MessageType(str, Enum):
    """Types of messages exchanged via WebSocket."""
    
    # Worker messages
    WORKER_REGISTER = "worker.register"
    WORKER_STATUS = "worker.status"
    WORKER_DEREGISTER = "worker.deregister"
    
    # Task messages
    TASK_ASSIGNMENT = "task.assignment"
    TASK_RESULT = "task.result"
    TASK_STATUS = "task.status"
    
    # Client messages
    CLIENT_SUBMIT = "client.submit"
    CLIENT_CANCEL = "client.cancel"
    
    # Server messages
    SERVER_CONFIG = "server.config"
    SERVER_ACK = "server.ack"
    SERVER_ERROR = "server.error"
    
    # Broadcast messages
    BROADCAST_STATUS = "broadcast.status"


class TaskStatus(str, Enum):
    """Status of a render task."""
    
    PENDING = "pending"
    ASSIGNED = "assigned"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkerInfo(BaseModel):
    """Information about a worker node."""
    
    worker_id: UUID = Field(..., description="Unique identifier for the worker")
    name: str = Field(..., description="Human-readable name for the worker")
    hostname: str = Field(..., description="Hostname of the worker machine")
    cpu_cores: int = Field(..., description="Number of CPU cores available")
    gpu_count: int = Field(..., description="Number of GPUs available")
    gpu_models: List[str] = Field(default_factory=list, description="List of GPU models")
    memory_gb: float = Field(..., description="Available memory in GB")
    blender_version: str = Field(..., description="Blender version installed")
    status: str = Field(default="idle", description="Current worker status")
    registered_at: datetime = Field(default_factory=datetime.utcnow, description="When the worker registered")
    last_ping: datetime = Field(default_factory=datetime.utcnow, description="Last ping timestamp")
    
    model_config = ConfigDict(from_attributes=True, json_schema_extra={"example": {
        "worker_id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "worker-01",
        "hostname": "render-node-01",
        "cpu_cores": 32,
        "gpu_count": 4,
        "gpu_models": ["RTX 4090"],
        "memory_gb": 128.0,
        "blender_version": "3.6.0",
        "status": "idle",
    }})


class ProjectInfo(BaseModel):
    """Information about a Blender project to render."""
    
    project_id: UUID = Field(..., description="Unique identifier for the project")
    project_name: str = Field(..., description="Name of the project")
    blender_file_path: str = Field(..., description="Path to the .blend file")
    output_path: str = Field(..., description="Path for output files")
    render_engine: str = Field(default="CYCLES", description="Render engine to use")
    resolution_x: int = Field(..., description="Render resolution X")
    resolution_y: int = Field(..., description="Render resolution Y")
    frame_start: int = Field(..., description="Start frame")
    frame_end: int = Field(..., description="End frame")
    frame_step: int = Field(default=1, description="Frame step")
    samples: int = Field(default=128, description="Number of samples per pixel")
    use_gpu: bool = Field(default=True, description="Whether to use GPU rendering")
    priority: int = Field(default=0, description="Priority level (higher = more priority)")
    client_id: Optional[UUID] = Field(default=None, description="Client who submitted the project")
    submitted_at: datetime = Field(default_factory=datetime.utcnow, description="When the project was submitted")
    
    model_config = ConfigDict(from_attributes=True, json_schema_extra={"example": {
        "project_id": "550e8400-e29b-41d4-a716-446655440001",
        "project_name": "my_project",
        "blender_file_path": "/projects/my_project.blend",
        "output_path": "/output/my_project",
        "render_engine": "CYCLES",
        "resolution_x": 1920,
        "resolution_y": 1080,
        "frame_start": 1,
        "frame_end": 100,
        "frame_step": 1,
        "samples": 128,
        "use_gpu": True,
        "priority": 0,
    }})


class RenderTask(BaseModel):
    """A single render task for a worker to execute."""
    
    task_id: UUID = Field(..., description="Unique identifier for the task")
    project_id: UUID = Field(..., description="Project this task belongs to")
    frame_number: int = Field(..., description="Frame number to render")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Current task status")
    assigned_worker_id: Optional[UUID] = Field(default=None, description="Worker assigned to this task")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When the task was created")
    started_at: Optional[datetime] = Field(default=None, description="When the task started processing")
    completed_at: Optional[datetime] = Field(default=None, description="When the task was completed")
    error_message: Optional[str] = Field(default=None, description="Error message if task failed")
    render_time_seconds: Optional[float] = Field(default=None, description="Time taken to render in seconds")
    
    model_config = ConfigDict(from_attributes=True, json_schema_extra={"example": {
        "task_id": "550e8400-e29b-41d4-a716-446655440002",
        "project_id": "550e8400-e29b-41d4-a716-446655440001",
        "frame_number": 1,
        "status": "pending",
        "assigned_worker_id": None,
    }})


class BaseMessage(BaseModel):
    """Base model for all WebSocket messages."""
    
    message_type: MessageType = Field(..., description="Type of the message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the message was sent")
    message_id: UUID = Field(default_factory=lambda: UUID(int=0), description="Unique message identifier")
    
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)
    
    def __init__(self, **data):
        super().__init__(**data)
        if self.message_id == UUID(int=0):
            self.message_id = UUID(int=0)  # Will be set properly when creating instances


class WorkerRegisterMessage(BaseMessage):
    """Message sent by a worker to register with the server."""
    
    message_type: MessageType = Field(default=MessageType.WORKER_REGISTER, description="Message type")
    worker_info: WorkerInfo = Field(..., description="Worker information")
    
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class WorkerStatusMessage(BaseMessage):
    """Message sent by a worker to update its status."""
    
    message_type: MessageType = Field(default=MessageType.WORKER_STATUS, description="Message type")
    worker_id: UUID = Field(..., description="Worker identifier")
    status: str = Field(..., description="Current worker status")
    current_task_id: Optional[UUID] = Field(default=None, description="Current task being processed")
    progress_percent: Optional[float] = Field(default=None, description="Progress percentage if processing")
    
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class WorkerDeregisterMessage(BaseMessage):
    """Message sent by a worker to deregister from the server."""
    
    message_type: MessageType = Field(default=MessageType.WORKER_DEREGISTER, description="Message type")
    worker_id: UUID = Field(..., description="Worker identifier")
    reason: Optional[str] = Field(default=None, description="Reason for deregistration")
    
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class TaskAssignmentMessage(BaseMessage):
    """Message sent by the server to assign a task to a worker."""
    
    message_type: MessageType = Field(default=MessageType.TASK_ASSIGNMENT, description="Message type")
    task: RenderTask = Field(..., description="Task to be executed")
    project_info: ProjectInfo = Field(..., description="Project information for context")
    
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class TaskResultMessage(BaseMessage):
    """Message sent by a worker to report task completion."""
    
    message_type: MessageType = Field(default=MessageType.TASK_RESULT, description="Message type")
    task_id: UUID = Field(..., description="Task identifier")
    worker_id: UUID = Field(..., description="Worker identifier")
    status: TaskStatus = Field(..., description="Final task status")
    output_file: Optional[str] = Field(default=None, description="Path to the rendered output file")
    render_time_seconds: Optional[float] = Field(default=None, description="Time taken to render")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    frame_number: int = Field(..., description="Frame number that was rendered")
    
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class TaskStatusMessage(BaseMessage):
    """Message to update the status of a task."""
    
    message_type: MessageType = Field(default=MessageType.TASK_STATUS, description="Message type")
    task_id: UUID = Field(..., description="Task identifier")
    status: TaskStatus = Field(..., description="New task status")
    worker_id: Optional[UUID] = Field(default=None, description="Worker identifier if applicable")
    progress_percent: Optional[float] = Field(default=None, description="Progress percentage")
    
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class ClientSubmitMessage(BaseMessage):
    """Message sent by a client to submit a new project."""
    
    message_type: MessageType = Field(default=MessageType.CLIENT_SUBMIT, description="Message type")
    client_id: Optional[UUID] = Field(default=None, description="Client identifier")
    project_info: ProjectInfo = Field(..., description="Project information")
    
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class ClientCancelMessage(BaseMessage):
    """Message sent by a client to cancel a project."""
    
    message_type: MessageType = Field(default=MessageType.CLIENT_CANCEL, description="Message type")
    client_id: Optional[UUID] = Field(default=None, description="Client identifier")
    project_id: UUID = Field(..., description="Project identifier to cancel")
    reason: Optional[str] = Field(default=None, description="Reason for cancellation")
    
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class ServerConfigMessage(BaseMessage):
    """Message sent by the server with configuration information."""
    
    message_type: MessageType = Field(default=MessageType.SERVER_CONFIG, description="Message type")
    server_name: str = Field(..., description="Server name")
    server_version: str = Field(..., description="Server version")
    max_workers: int = Field(..., description="Maximum number of workers")
    queue_size: int = Field(..., description="Current queue size")
    active_tasks: int = Field(..., description="Number of active tasks")
    
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class ServerAckMessage(BaseMessage):
    """Acknowledgment message from the server."""
    
    message_type: MessageType = Field(default=MessageType.SERVER_ACK, description="Message type")
    in_response_to: Optional[UUID] = Field(default=None, description="Message ID this is responding to")
    success: bool = Field(..., description="Whether the operation was successful")
    message: Optional[str] = Field(default=None, description="Additional message")
    
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class ServerErrorMessage(BaseMessage):
    """Error message from the server."""
    
    message_type: MessageType = Field(default=MessageType.SERVER_ERROR, description="Message type")
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Error description")
    in_response_to: Optional[UUID] = Field(default=None, description="Message ID this is responding to")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
    
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class BroadcastStatusMessage(BaseMessage):
    """Broadcast message with system status."""
    
    message_type: MessageType = Field(default=MessageType.BROADCAST_STATUS, description="Message type")
    total_workers: int = Field(..., description="Total registered workers")
    active_workers: int = Field(..., description="Number of active workers")
    pending_tasks: int = Field(..., description="Number of pending tasks")
    processing_tasks: int = Field(..., description="Number of processing tasks")
    completed_tasks: int = Field(..., description="Number of completed tasks")
    worker_summaries: List[Dict[str, Any]] = Field(default_factory=list, description="Summary of each worker")
    
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


def create_message(
    message_type: MessageType,
    message_id: Optional[UUID] = None,
    **kwargs
) -> BaseMessage:
    """Factory function to create messages with proper IDs."""
    message_class = {
        MessageType.WORKER_REGISTER: WorkerRegisterMessage,
        MessageType.WORKER_STATUS: WorkerStatusMessage,
        MessageType.WORKER_DEREGISTER: WorkerDeregisterMessage,
        MessageType.TASK_ASSIGNMENT: TaskAssignmentMessage,
        MessageType.TASK_RESULT: TaskResultMessage,
        MessageType.TASK_STATUS: TaskStatusMessage,
        MessageType.CLIENT_SUBMIT: ClientSubmitMessage,
        MessageType.CLIENT_CANCEL: ClientCancelMessage,
        MessageType.SERVER_CONFIG: ServerConfigMessage,
        MessageType.SERVER_ACK: ServerAckMessage,
        MessageType.SERVER_ERROR: ServerErrorMessage,
        MessageType.BROADCAST_STATUS: BroadcastStatusMessage,
    }.get(message_type, BaseMessage)
    
    data = {"message_type": message_type, "message_id": message_id or UUID(int=0)}
    data.update(kwargs)
    
    if message_class == BaseMessage:
        return BaseMessage(**data)
    
    return message_class(**data)
