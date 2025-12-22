# Cortex Linux - Official Docker Image
# Base image: Python 3.11 on Debian Bookworm (slim)
FROM python:3.11-slim-bookworm

# Set metadata
LABEL maintainer="mike@cortexlinux.com"
LABEL description="AI-powered package manager for Debian/Ubuntu that understands natural language"
LABEL org.opencontainers.image.source="https://github.com/cortexlinux/cortex"

# Set working directory
WORKDIR /app

# Install system dependencies (minimal - only what's needed)
# Note: apt is available in the base image, but we don't need additional packages
# for Cortex itself. Users can install packages via Cortex if needed.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    sudo \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 cortex && \
    echo "cortex ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/cortex && \
    chmod 0440 /etc/sudoers.d/cortex

# Copy requirements first for better layer caching
COPY requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy Cortex source code
COPY . /app/

# Install Cortex in editable mode
RUN pip install --no-cache-dir -e .

# Set up environment
ENV PYTHONUNBUFFERED=1
ENV CORTEX_DOCKER=1

# Switch to non-root user
USER cortex
WORKDIR /app

# Configure entrypoint to handle command passthrough
# Usage: docker run cortexlinux/cortex install nginx --dry-run
ENTRYPOINT ["cortex"]

# Default command (can be overridden)
CMD ["--help"]
