"""Tests for Pydantic schemas."""

import pytest
from uuid import UUID
from datetime import datetime

from cactus_tools.schemas import (
    MessageType,
    TaskStatus,
    WorkerInfo,
    ProjectInfo,
    RenderTask,
    BaseMessage,
    WorkerRegisterMessage,
    WorkerStatusMessage,
    TaskAssignmentMessage,
    TaskResultMessage,
    ClientSubmitMessage,
    ServerConfigMessage,
    ServerAckMessage,
    create_message,
)


class TestMessageTypes:
    """Test message type enum."""
    
    def test_message_type_values(self):
        """Test that message types have correct values."""
        assert MessageType.WORKER_REGISTER == "worker.register"
        assert MessageType.WORKER_STATUS == "worker.status"
        assert MessageType.TASK_ASSIGNMENT == "task.assignment"
        assert MessageType.TASK_RESULT == "task.result"
        assert MessageType.CLIENT_SUBMIT == "client.submit"
        assert MessageType.SERVER_CONFIG == "server.config"


class TestTaskStatus:
    """Test task status enum."""
    
    def test_task_status_values(self):
        """Test that task statuses have correct values."""
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.ASSIGNED == "assigned"
        assert TaskStatus.PROCESSING == "processing"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.CANCELLED == "cancelled"


class TestWorkerInfo:
    """Test WorkerInfo schema."""
    
    def test_worker_info_creation(self):
        """Test creating a WorkerInfo instance."""
        worker = WorkerInfo(
            worker_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            name="worker-01",
            hostname="render-node-01",
            cpu_cores=32,
            gpu_count=4,
            memory_gb=128.0,
            blender_version="3.6.0",
        )
        
        assert worker.worker_id == UUID("550e8400-e29b-41d4-a716-446655440000")
        assert worker.name == "worker-01"
        assert worker.hostname == "render-node-01"
        assert worker.cpu_cores == 32
        assert worker.gpu_count == 4
        assert worker.memory_gb == 128.0
        assert worker.blender_version == "3.6.0"
        assert worker.status == "idle"
    
    def test_worker_info_serialization(self):
        """Test serializing WorkerInfo to JSON."""
        worker = WorkerInfo(
            worker_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            name="worker-01",
            hostname="render-node-01",
            cpu_cores=32,
            gpu_count=4,
            memory_gb=128.0,
            blender_version="3.6.0",
        )
        
        json_data = worker.model_dump_json()
        assert "worker-01" in json_data
        assert "550e8400-e29b-41d4-a716-446655440000" in json_data


class TestProjectInfo:
    """Test ProjectInfo schema."""
    
    def test_project_info_creation(self):
        """Test creating a ProjectInfo instance."""
        project = ProjectInfo(
            project_id=UUID("550e8400-e29b-41d4-a716-446655440001"),
            project_name="my_project",
            blender_file_path="/projects/my_project.blend",
            output_path="/output/my_project",
            resolution_x=1920,
            resolution_y=1080,
            frame_start=1,
            frame_end=100,
        )
        
        assert project.project_id == UUID("550e8400-e29b-41d4-a716-446655440001")
        assert project.project_name == "my_project"
        assert project.resolution_x == 1920
        assert project.resolution_y == 1080
        assert project.frame_start == 1
        assert project.frame_end == 100


class TestRenderTask:
    """Test RenderTask schema."""
    
    def test_render_task_creation(self):
        """Test creating a RenderTask instance."""
        task = RenderTask(
            task_id=UUID("550e8400-e29b-41d4-a716-446655440002"),
            project_id=UUID("550e8400-e29b-41d4-a716-446655440001"),
            frame_number=1,
        )
        
        assert task.task_id == UUID("550e8400-e29b-41d4-a716-446655440002")
        assert task.project_id == UUID("550e8400-e29b-41d4-a716-446655440001")
        assert task.frame_number == 1
        assert task.status == TaskStatus.PENDING


class TestWorkerRegisterMessage:
    """Test WorkerRegisterMessage schema."""
    
    def test_worker_register_message(self):
        """Test creating a WorkerRegisterMessage."""
        worker_info = WorkerInfo(
            worker_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            name="worker-01",
            hostname="render-node-01",
            cpu_cores=32,
            gpu_count=4,
            memory_gb=128.0,
            blender_version="3.6.0",
        )
        
        message = WorkerRegisterMessage(worker_info=worker_info)
        
        assert message.message_type == MessageType.WORKER_REGISTER
        assert message.worker_info.name == "worker-01"


class TestTaskResultMessage:
    """Test TaskResultMessage schema."""
    
    def test_task_result_message_completed(self):
        """Test creating a completed TaskResultMessage."""
        message = TaskResultMessage(
            task_id=UUID("550e8400-e29b-41d4-a716-446655440002"),
            worker_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            status=TaskStatus.COMPLETED,
            output_file="/output/frame_0001.png",
            render_time_seconds=120.5,
            frame_number=1,
        )
        
        assert message.message_type == MessageType.TASK_RESULT
        assert message.status == TaskStatus.COMPLETED
        assert message.output_file == "/output/frame_0001.png"
        assert message.render_time_seconds == 120.5
    
    def test_task_result_message_failed(self):
        """Test creating a failed TaskResultMessage."""
        message = TaskResultMessage(
            task_id=UUID("550e8400-e29b-41d4-a716-446655440002"),
            worker_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            status=TaskStatus.FAILED,
            error_message="Out of memory",
            frame_number=1,
        )
        
        assert message.status == TaskStatus.FAILED
        assert message.error_message == "Out of memory"


class TestClientSubmitMessage:
    """Test ClientSubmitMessage schema."""
    
    def test_client_submit_message(self):
        """Test creating a ClientSubmitMessage."""
        project_info = ProjectInfo(
            project_id=UUID("550e8400-e29b-41d4-a716-446655440001"),
            project_name="my_project",
            blender_file_path="/projects/my_project.blend",
            output_path="/output/my_project",
            resolution_x=1920,
            resolution_y=1080,
            frame_start=1,
            frame_end=100,
        )
        
        message = ClientSubmitMessage(project_info=project_info)
        
        assert message.message_type == MessageType.CLIENT_SUBMIT
        assert message.project_info.project_name == "my_project"


class TestServerConfigMessage:
    """Test ServerConfigMessage schema."""
    
    def test_server_config_message(self):
        """Test creating a ServerConfigMessage."""
        message = ServerConfigMessage(
            server_name="Cactus Server",
            server_version="0.1.0",
            max_workers=100,
            queue_size=10,
            active_tasks=5,
        )
        
        assert message.message_type == MessageType.SERVER_CONFIG
        assert message.server_name == "Cactus Server"
        assert message.max_workers == 100


class TestCreateMessage:
    """Test create_message factory function."""
    
    def test_create_worker_register_message(self):
        """Test creating a WorkerRegisterMessage with factory."""
        worker_info = WorkerInfo(
            worker_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            name="worker-01",
            hostname="render-node-01",
            cpu_cores=32,
        )
        
        message = create_message(
            MessageType.WORKER_REGISTER,
            worker_info=worker_info,
        )
        
        assert isinstance(message, WorkerRegisterMessage)
        assert message.message_type == MessageType.WORKER_REGISTER


class TestMessageSerialization:
    """Test message serialization and deserialization."""
    
    def test_roundtrip_worker_register(self):
        """Test roundtrip serialization for WorkerRegisterMessage."""
        worker_info = WorkerInfo(
            worker_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            name="worker-01",
            hostname="render-node-01",
            cpu_cores=32,
        )
        
        original = WorkerRegisterMessage(worker_info=worker_info)
        json_data = original.model_dump_json()
        restored = WorkerRegisterMessage.model_validate_json(json_data)
        
        assert restored.worker_info.name == original.worker_info.name
        assert restored.worker_info.worker_id == original.worker_info.worker_id
    
    def test_roundtrip_task_result(self):
        """Test roundtrip serialization for TaskResultMessage."""
        original = TaskResultMessage(
            task_id=UUID("550e8400-e29b-41d4-a716-446655440002"),
            worker_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            status=TaskStatus.COMPLETED,
            output_file="/output/frame_0001.png",
            frame_number=1,
        )
        
        json_data = original.model_dump_json()
        restored = TaskResultMessage.model_validate_json(json_data)
        
        assert restored.task_id == original.task_id
        assert restored.status == original.status
        assert restored.output_file == original.output_file
