# Docker Configuration for Blender Cactus

This directory contains Docker configuration files for running Blender Cactus render farm using containerized environments.

## Base Image

All Dockerfiles use **`ghcr.io/astral-sh/uv:debian-slim`** as the base image, which provides:
- Python with uv (Astral's fast Python package installer)
- Debian slim base for minimal footprint
- Optimized for Python applications

## Available Images

### 1. Cactus Server

**Dockerfile:** `cactus-server/Dockerfile`

**Purpose:** Runs the central server that manages workers and distributes tasks

**Build:**
```bash
# Build the server image
docker build -t cactus-server -f cactus-server/Dockerfile .

# Run the server
docker run -d \
  --name cactus-server \
  -p 8000:8000 \
  -e CACTUS_SERVER_HOST=0.0.0.0 \
  -e CACTUS_SERVER_PORT=8000 \
  cactus-server
```

**Environment Variables:**
```bash
CACTUS_SERVER_HOST=0.0.0.0    # Server host
CACTUS_SERVER_PORT=8000       # Server port
CACTUS_MAX_WORKERS=100        # Maximum workers
CACTUS_LOG_LEVEL=INFO        # Log level
```

### 2. Cactus Worker

**Dockerfile:** `cactus-worker/Dockerfile`

**Purpose:** Runs a worker that connects to the server and processes render tasks

**Build:**
```bash
# Build the worker image
docker build -t cactus-worker -f cactus-worker/Dockerfile .

# Run a worker
docker run -d \
  --name cactus-worker-1 \
  -e CACTUS_SERVER_HOST=server \
  -e CACTUS_SERVER_PORT=8000 \
  -e CACTUS_WORKER_NAME=worker-1 \
  cactus-worker
```

**Environment Variables:**
```bash
CACTUS_SERVER_HOST=server       # Server host to connect to
CACTUS_SERVER_PORT=8000        # Server port
CACTUS_WORKER_NAME=worker-1    # Worker name
CACTUS_BLENDER_PATH=blender    # Path to Blender executable
CACTUS_LOG_LEVEL=INFO         # Log level
```

### 3. Cactus Tools

**Dockerfile:** `cactus-tools/Dockerfile`

**Purpose:** Base image with common tools and schemas (for development/testing)

**Build:**
```bash
# Build the tools image
docker build -t cactus-tools -f cactus-tools/Dockerfile .
```

## Docker Compose

The easiest way to run the entire render farm is using Docker Compose:

```bash
# Start the full stack (1 server + 3 workers)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the stack
docker-compose down

# Scale workers
docker-compose up -d --scale worker=5
```

### Services

- **server**: Central server on port 8000
- **worker-1, worker-2, worker-3**: Worker nodes that connect to the server
- **cactus-network**: Dedicated network for communication

### Custom Configuration

Edit `docker-compose.yml` to:
- Change the number of workers
- Modify environment variables
- Add volume mounts for output files
- Configure ports

## Build All Images

```bash
# Build all images
docker-compose build

# Or build individually
docker build -t cactus-server -f cactus-server/Dockerfile .
docker build -t cactus-worker -f cactus-worker/Dockerfile .
docker build -t cactus-tools -f cactus-tools/Dockerfile .
```

## Development with Docker

### Run tests in container

```bash
# Run tests for a specific module
docker run --rm \
  -v $(pwd):/app \
  -w /app/cactus-tools \
  cactus-tools \
  python -m pytest tests/ -v
```

### Shell access

```bash
# Access server container
docker exec -it cactus-server /bin/bash

# Access worker container
docker exec -it cactus-worker-1 /bin/bash
```

## Production Deployment

### Using Docker Swarm

```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml cactus
```

### Using Kubernetes

Convert the docker-compose.yml to Kubernetes manifests using tools like `kompose`:

```bash
kompose convert -f docker-compose.yml -o kubernetes/
```

## Blender Configuration

For the workers to render, you need Blender installed. Options:

### Option 1: Install Blender in container

Modify the worker Dockerfile:
```dockerfile
FROM ghcr.io/astral-sh/uv:debian-slim

# Install Blender
RUN apt-get update && apt-get install -y wget && \
    wget https://download.blender.org/release/Blender3.6/blender-3.6.0-linux-x64.tar.xz && \
    tar -xf blender-*.tar.xz && \
    mv blender-*/blender /usr/local/bin/ && \
    rm blender-*.tar.xz && \
    apt-get clean
```

### Option 2: Mount Blender from host

In docker-compose.yml:
```yaml
volumes:
  - /usr/bin/blender:/usr/bin/blender:ro
```

### Option 3: Use a custom Blender image

Create a custom image with Blender pre-installed and use it as the base for workers.

## Environment Variables Reference

### Server
| Variable | Default | Description |
|----------|---------|-------------|
| `CACTUS_SERVER_HOST` | 0.0.0.0 | Server host address |
| `CACTUS_SERVER_PORT` | 8000 | Server port |
| `CACTUS_MAX_WORKERS` | 100 | Maximum number of workers |
| `CACTUS_WEBSOCKET_PATH` | /ws | WebSocket endpoint path |
| `CACTUS_LOG_LEVEL` | INFO | Logging level |

### Worker
| Variable | Default | Description |
|----------|---------|-------------|
| `CACTUS_SERVER_HOST` | localhost | Server host to connect to |
| `CACTUS_SERVER_PORT` | 8000 | Server port |
| `CACTUS_WORKER_NAME` | auto | Worker name |
| `CACTUS_BLENDER_PATH` | blender | Path to Blender executable |
| `CACTUS_TEMP_DIR` | /tmp/cactus | Temporary directory |
| `CACTUS_OUTPUT_DIR` | /output/cactus | Output directory |
| `CACTUS_LOG_LEVEL` | INFO | Logging level |

## Troubleshooting

### Workers can't connect to server

Check:
1. Server is running: `docker-compose logs server`
2. Workers are running: `docker-compose logs worker-1`
3. Network connectivity: `docker network inspect cactus-network`
4. Server host is correct (use `server` as hostname in Docker Compose)

### Blender not found

Ensure:
1. Blender is installed in the container or mounted from host
2. `CACTUS_BLENDER_PATH` points to the correct location
3. The Blender executable has execute permissions

### Build failures

Try:
```bash
# Clean build
docker-compose build --no-cache

# Check disk space
docker system df

# Prune unused objects
docker system prune
```

## Performance Tips

1. **Use build cache**: Docker will cache layers for faster rebuilds
2. **Multi-stage builds**: Consider multi-stage builds for production
3. **Scale workers**: Use `docker-compose up -d --scale worker=N`
4. **Resource limits**: Set CPU/memory limits in docker-compose.yml

## Security

1. **Use non-root user**: All containers run as `appuser` (UID 1000)
2. **Read-only filesystems**: Consider adding `:ro` to volume mounts
3. **Network isolation**: Use dedicated networks
4. **Secrets management**: Use Docker secrets or environment files for sensitive data
