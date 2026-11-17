# Cactus Tools

Common tools and schemas for Blender Cactus render farm.

## Overview

This package contains the Pydantic schemas used for WebSocket communication between the server, workers, and clients in the Blender Cactus render farm.

## Installation

```bash
# Using UV
uv pip install -e .

# Or using pip
pip install -e .
```

## Schemas

### Message Types

- `MessageType`: Enum defining all possible message types
- `TaskStatus`: Enum defining task status values

### Worker Messages

- `WorkerInfo`: Information about a worker node
- `WorkerRegisterMessage`: Message sent by worker to register
- `WorkerStatusMessage`: Message to update worker status
- `WorkerDeregisterMessage`: Message to deregister a worker

### Task Messages

- `RenderTask`: A single render task
- `TaskAssignmentMessage`: Server assigns task to worker
- `TaskResultMessage`: Worker reports task completion
- `TaskStatusMessage`: Update task status

### Client Messages

- `ProjectInfo`: Information about a Blender project
- `ClientSubmitMessage`: Client submits a new project
- `ClientCancelMessage`: Client cancels a project

### Server Messages

- `ServerConfigMessage`: Server configuration
- `ServerAckMessage`: Acknowledgment message
- `ServerErrorMessage`: Error message from server
- `BroadcastStatusMessage`: System status broadcast

## Usage

```python
from cactus_tools import WorkerRegisterMessage, WorkerInfo
from uuid import UUID

# Create a worker info
worker_info = WorkerInfo(
    worker_id=UUID(),
    name="worker-01",
    hostname="render-node-01",
    cpu_cores=32,
    gpu_count=4,
    memory_gb=128.0,
    blender_version="3.6.0",
)

# Create a register message
register_msg = WorkerRegisterMessage(worker_info=worker_info)

# Serialize to JSON
json_data = register_msg.model_dump_json()

# Deserialize from JSON
from cactus_tools import BaseMessage
message = BaseMessage.model_validate_json(json_data)
```
