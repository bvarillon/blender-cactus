# Blender Cactus - Base Dockerfile
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

# Copy project files
COPY . .

# Install all packages in development mode
RUN uv pip install -e ".[all]" && \
    chown -R appuser:appuser /app

# Switch to app user
USER appuser

# Expose ports (server default)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import cactus_server; print('OK')" || exit 1

# Default command
CMD ["python", "-m", "cactus_server.server"]
