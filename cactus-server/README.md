# Cactus Server

Server for Blender Cactus render farm.

## Overview

The Cactus Server is the central controller for the render farm. It:
- Accepts WebSocket connections from workers and clients
- Manages worker registration and status
- Distributes render tasks to available workers
- Tracks task progress and results
- Provides status updates to clients

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
# Server settings
CACTUS_SERVER_HOST=0.0.0.0
CACTUS_SERVER_PORT=8000
CACTUS_SERVER_NAME="Cactus Server"
CACTUS_SERVER_VERSION="0.1.0"

# WebSocket settings
CACTUS_WEBSOCKET_PATH=/ws
CACTUS_WEBSOCKET_PING_INTERVAL=30
CACTUS_WEBSOCKET_PING_TIMEOUT=60

# Worker settings
CACTUS_MAX_WORKERS=100
CACTUS_WORKER_TIMEOUT=300

# Task settings
CACTUS_MAX_QUEUE_SIZE=1000
CACTUS_TASK_TIMEOUT=3600

# Logging
CACTUS_LOG_LEVEL=INFO
```

## Running the Server

```bash
# Using the module directly
python -m cactus_server.server

# Or using the create_server function
from cactus_server import create_server
server = create_server()
asyncio.run(server.run())
```

## API

### WebSocket Endpoints

- `/ws`: Main WebSocket endpoint for all communication

### HTTP Endpoints

- `GET /`: Basic server info
- `GET /status`: Detailed server status

## Architecture

### Components

- `CactusServer`: Main server class
- `ConnectionManager`: Manages WebSocket connections
- `WorkerManager`: Manages worker connections and status
- `TaskQueue`: Manages the queue of render tasks

### Message Flow

1. **Worker Registration**: Worker connects via WebSocket, sends `WorkerRegisterMessage`
2. **Task Assignment**: Server assigns tasks via `TaskAssignmentMessage`
3. **Task Processing**: Worker processes task and sends `TaskResultMessage`
4. **Client Submission**: Client connects via WebSocket, sends `ClientSubmitMessage`
5. **Status Updates**: Server broadcasts `BroadcastStatusMessage` to all clients

## Usage with Frontend

The server communicates with the frontend via WebSocket. Clients can:
- Submit new projects with `ClientSubmitMessage`
- Cancel projects with `ClientCancelMessage`
- Receive status updates via `BroadcastStatusMessage`

## Dependencies

- Python 3.11+
- FastAPI
- Uvicorn
- WebSockets
- cactus-tools
