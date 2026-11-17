# Cactus Server Dockerfile
# Uses uv:debian-slim as the base image

FROM ghcr.io/astral-sh/uv:debian-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create app user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY pyproject.toml ./

# Install server dependencies
RUN uv pip install --system -e ".[dev]" && \
    rm -rf /tmp/*

# Copy the rest of the application
COPY . .

# Set permissions
RUN chown -R appuser:appuser /app

# Switch to app user
USER appuser

# Expose server port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from cactus_server import CactusServer; print('Server OK')" || exit 1

# Default command - run the server
CMD ["python", "-m", "cactus_server.server"]
