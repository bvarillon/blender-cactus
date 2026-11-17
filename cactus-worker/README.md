# Cactus Worker

Worker for Blender Cactus render farm.

## Overview

The Cactus Worker is a node in the render farm that:
- Connects to the Cactus Server via WebSocket
- Registers its capabilities (CPU, GPU, memory, Blender version)
- Receives render tasks from the server
- Renders Blender frames using the local Blender installation
- Reports task results back to the server

## Installation

```bash
# Using UV
uv pip install -e .

# Or using pip
pip install -e .
```

## Configuration

Create a `.env` file or set environment variables:

```bash
# Server connection
CACTUS_SERVER_HOST=localhost
CACTUS_SERVER_PORT=8000
CACTUS_SERVER_WEBSOCKET_PATH=/ws

# Worker identity
CACTUS_WORKER_NAME=worker-01
CACTUS_WORKER_ID=

# Blender settings
CACTUS_BLENDER_PATH=blender
CACTUS_BLENDER_VERSION=3.6.0

# Render settings
CACTUS_TEMP_DIR=/tmp/cactus
CACTUS_OUTPUT_DIR=/output/cactus

# System detection
CACTUS_AUTO_DETECT_GPU=true
CACTUS_AUTO_DETECT_CPU=true

# Connection settings
CACTUS_RECONNECT_INTERVAL=5
CACTUS_PING_INTERVAL=30

# Logging
CACTUS_LOG_LEVEL=INFO
```

## Running the Worker

```bash
# Using the module directly
python -m cactus_worker.worker

# Or using the create_worker function
from cactus_worker import create_worker
worker = create_worker()
asyncio.run(worker.run())
```

## Blender Configuration

The worker uses the local Blender installation to render frames. Ensure:

1. Blender is installed and accessible via the `blender_path` setting
2. The Blender version supports command-line rendering
3. Required add-ons are installed (if any)

### Command Line Rendering

The worker uses Blender's command-line interface:

```bash
blender file.blend --background --render-frame 1 --output output.png
```

## Features

### Automatic System Detection

The worker automatically detects:
- CPU cores
- Available memory
- GPU count and models (NVIDIA only, requires pynvml or nvidia-smi)
- Blender version

### Render Settings

The worker supports:
- Multiple render engines (CYCLES, EVEE, etc.)
- Custom resolutions
- GPU and CPU rendering
- Custom sample counts

### Error Handling

The worker handles:
- Connection errors (automatic reconnection)
- Blender rendering errors
- Task timeouts
- Invalid messages

## Architecture

### Components

- `CactusWorker`: Main worker class
- `WorkerConfig`: Configuration settings
- `BlenderRenderer`: Handles Blender rendering

### Message Flow

1. **Connection**: Worker connects to server WebSocket
2. **Registration**: Worker sends `WorkerRegisterMessage` with capabilities
3. **Task Assignment**: Server sends `TaskAssignmentMessage`
4. **Task Processing**: Worker renders frame using `BlenderRenderer`
5. **Result Reporting**: Worker sends `TaskResultMessage` with results
6. **Status Updates**: Worker sends `WorkerStatusMessage` periodically

## Dependencies

- Python 3.11+
- WebSockets
- cactus-tools

### Optional Dependencies

- `pynvml`: For NVIDIA GPU detection
- `psutil`: For accurate memory detection

## Multiple Workers

Run multiple workers on the same machine by:
1. Creating separate configuration files
2. Using different worker names
3. Running multiple instances with different environment variables

```bash
# Worker 1
CACTUS_WORKER_NAME=worker-01 CACTUS_SERVER_PORT=8000 python -m cactus_worker.worker &

# Worker 2
CACTUS_WORKER_NAME=worker-02 CACTUS_SERVER_PORT=8000 python -m cactus_worker.worker &
```
