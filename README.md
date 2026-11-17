# Blender Cactus Render Farm

A distributed render farm for Blender using WebSocket communication.

## Overview

Blender Cactus is a render farm system that allows you to distribute Blender rendering across multiple machines. It consists of:

- **cactus-server**: Central server that manages workers and distributes tasks
- **cactus-worker**: Worker nodes that perform the actual rendering
- **cactus-tools**: Common schemas and utilities for communication
- **app**: Frontend web interface for submitting and monitoring projects

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Client    │    │   Client    │    │   Client    │
│  (Browser)  │    │  (Browser)  │    │  (Browser)  │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                    │                    │
       ▼                    ▼                    ▼
┌───────────────────────────────────────────────────────┐
│                   Cactus Server                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │ WebSocket   │  │  Task Queue │  │ Worker Mgr  │   │
│  │  Handler    │  │             │  │             │   │
│  └─────────────┘  └─────────────┘  └─────────────┘   │
└───────────────────────────────────────────────────────┘
       │                    │                    │
       ▼                    ▼                    ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Worker 1   │    │  Worker 2   │    │  Worker N   │
│             │    │             │    │             │
│  ┌─────────┐│    │  ┌─────────┐│    │  ┌─────────┐│
│  │ Blender ││    │  │ Blender ││    │  │ Blender ││
│  │ Render  ││    │  │ Render  ││    │  │ Render  ││
│  └─────────┘│    │  └─────────┘│    │  └─────────┘│
└─────────────┘    └─────────────┘    └─────────────┘
```

## Communication

All communication between components uses WebSocket with JSON messages validated by Pydantic schemas.

### Message Types

- **Worker Registration**: Workers register with the server, providing their capabilities
- **Task Assignment**: Server assigns render tasks to idle workers
- **Task Results**: Workers report completed or failed tasks
- **Client Submission**: Clients submit new projects for rendering
- **Status Updates**: Server broadcasts system status to all clients

## Quick Start

### 1. Install Dependencies

```bash
# Install UV if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or use pip
pip install uv
```

### 2. Setup the Project

```bash
# Clone the repository
git clone https://github.com/bvarillon/blender-cactus.git
cd blender-cactus

# Install all packages in development mode
uv pip install -e ".[all]"
```

### 3. Start the Server

```bash
# Navigate to server directory
cd cactus-server

# Start the server
uv pip install -e .
python -m cactus_server.server

# Or with custom configuration
CACTUS_SERVER_HOST=0.0.0.0 CACTUS_SERVER_PORT=8000 python -m cactus_server.server
```

### 4. Start Workers

```bash
# Navigate to worker directory
cd cactus-worker

# Start a worker
uv pip install -e .
python -m cactus_worker.worker

# Or with custom configuration
CACTUS_SERVER_HOST=localhost CACTUS_SERVER_PORT=8000 python -m cactus_worker.worker
```

### 5. Start Multiple Workers

```bash
# Worker 1
CACTUS_WORKER_NAME=worker-01 python -m cactus_worker.worker &

# Worker 2
CACTUS_WORKER_NAME=worker-02 python -m cactus_worker.worker &

# Worker 3
CACTUS_WORKER_NAME=worker-03 python -m cactus_worker.worker &
```

## Project Structure

```
blender-cactus/
├── cactus-tools/           # Common schemas and utilities
│   ├── src/cactus_tools/
│   │   ├── __init__.py
│   │   └── schemas.py      # Pydantic schemas for WebSocket messages
│   └── pyproject.toml
│
├── cactus-server/          # Central server
│   ├── src/cactus_server/
│   │   ├── __init__.py
│   │   ├── config.py       # Server configuration
│   │   ├── server.py       # Main server implementation
│   │   ├── worker_manager.py # Worker management
│   │   └── task_queue.py   # Task queue management
│   └── pyproject.toml
│
├── cactus-worker/          # Worker nodes
│   ├── src/cactus_worker/
│   │   ├── __init__.py
│   │   ├── config.py       # Worker configuration
│   │   ├── worker.py       # Main worker implementation
│   │   └── blender_renderer.py # Blender rendering
│   └── pyproject.toml
│
├── app/                    # Frontend (Vue.js)
│
└── pyproject.toml          # Root project configuration
```

## Configuration

### Server Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CACTUS_SERVER_HOST` | 0.0.0.0 | Server host address |
| `CACTUS_SERVER_PORT` | 8000 | Server port |
| `CACTUS_MAX_WORKERS` | 100 | Maximum number of workers |
| `CACTUS_MAX_QUEUE_SIZE` | 1000 | Maximum task queue size |

### Worker Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CACTUS_SERVER_HOST` | localhost | Server host to connect to |
| `CACTUS_SERVER_PORT` | 8000 | Server port |
| `CACTUS_WORKER_NAME` | auto | Worker name |
| `CACTUS_BLENDER_PATH` | blender | Path to Blender executable |
| `CACTUS_TEMP_DIR` | /tmp/cactus | Temporary directory |
| `CACTUS_OUTPUT_DIR` | /output/cactus | Output directory |

## WebSocket API

### Messages

#### Worker -> Server

- **WorkerRegisterMessage**: Register a new worker
  ```json
  {
    "message_type": "worker.register",
    "worker_info": {
      "worker_id": "uuid",
      "name": "worker-01",
      "hostname": "render-node-01",
      "cpu_cores": 32,
      "gpu_count": 4,
      "memory_gb": 128.0,
      "blender_version": "3.6.0"
    }
  }
  ```

- **WorkerStatusMessage**: Update worker status
  ```json
  {
    "message_type": "worker.status",
    "worker_id": "uuid",
    "status": "idle",
    "current_task_id": null,
    "progress_percent": 0.0
  }
  ```

- **TaskResultMessage**: Report task completion
  ```json
  {
    "message_type": "task.result",
    "task_id": "uuid",
    "worker_id": "uuid",
    "status": "completed",
    "output_file": "/output/frame_0001.png",
    "render_time_seconds": 120.5,
    "frame_number": 1
  }
  ```

#### Server -> Worker

- **TaskAssignmentMessage**: Assign a task to a worker
  ```json
  {
    "message_type": "task.assignment",
    "task": {
      "task_id": "uuid",
      "project_id": "uuid",
      "frame_number": 1,
      "status": "pending"
    },
    "project_info": {
      "project_id": "uuid",
      "project_name": "my_project",
      "blender_file_path": "/projects/my_project.blend",
      "output_path": "/output/my_project",
      "render_engine": "CYCLES",
      "resolution_x": 1920,
      "resolution_y": 1080
    }
  }
  ```

#### Client -> Server

- **ClientSubmitMessage**: Submit a new project
  ```json
  {
    "message_type": "client.submit",
    "project_info": {
      "project_id": "uuid",
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
      "use_gpu": true
    }
  }
  ```

#### Server -> Client

- **BroadcastStatusMessage**: System status update
  ```json
  {
    "message_type": "broadcast.status",
    "total_workers": 5,
    "active_workers": 3,
    "pending_tasks": 10,
    "processing_tasks": 3,
    "completed_tasks": 50,
    "worker_summaries": [...]
  }
  ```

## Development

### Project Setup

```bash
# Install all packages in development mode
uv pip install -e cactus-tools[dev]
uv pip install -e cactus-server[dev]
uv pip install -e cactus-worker[dev]
```

### Running Tests

```bash
# Run tests for all packages
cd cactus-tools && pytest
cd cactus-server && pytest
cd cactus-worker && pytest
```

### Code Quality

```bash
# Run ruff linter
ruff check cactus-tools cactus-server cactus-worker

# Run mypy type checker
mypy cactus-tools cactus-server cactus-worker
```

## Blender Configuration

### Required Blender Settings

1. **Command-line rendering**: Ensure Blender is installed and accessible from the command line
2. **Background mode**: Blender must support `--background` mode
3. **Frame rendering**: Blender must support `--render-frame` option

### Recommended Blender Settings

```python
# In your Blender file, ensure:
# - Render engine is set (CYCLES, EVEE, etc.)
# - Resolution is configured
# - Output path is set
# - Samples are configured
# - GPU rendering is enabled (if using GPU)
```

## Deployment

### Docker (Coming Soon)

### Systemd Service (Example)

```ini
# /etc/systemd/system/cactus-server.service
[Unit]
Description=Cactus Render Farm Server
After=network.target

[Service]
User=cactus
Group=cactus
WorkingDirectory=/opt/cactus/cactus-server
Environment="CACTUS_SERVER_HOST=0.0.0.0"
Environment="CACTUS_SERVER_PORT=8000"
ExecStart=/usr/bin/python -m cactus_server.server
Restart=always

[Install]
WantedBy=multi-user.target
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting pull requests.

## Support

For issues and questions, please open an issue on GitHub.
