# Multi-stage build for job scraper application
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    ENVIRONMENT=production

# Install system dependencies for Playwright and app
RUN apt-get update && apt-get install -y \
    # Core system packages
    wget \
    gnupg \
    ca-certificates \
    build-essential \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    python3-dev \
    # Playwright browser dependencies
    fonts-liberation \
    fonts-unifont \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcairo2 \
    libcups2 \
    libdrm2 \
    libfontconfig1 \
    libgdk-pixbuf-2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libxss1 \
    libxtst6 \
    libxrandr2 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxi6 \
    libxfixes3 \
    libxrender1 \
    libx11-xcb1 \
    libxcb-dri3-0 \
    libxcb1 \
    xdg-utils \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd --create-home --shell /bin/bash app

# Set work directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers and dependencies
RUN playwright install chromium
RUN playwright install-deps chromium || echo "Some deps may be missing but continuing..."

# Copy application code
COPY . .

# Create necessary directories with correct permissions
RUN mkdir -p data/{input,output,temp,logs,backup} && \
    chmod -R 777 data && \
    chown -R app:app /app

# Switch to app user
USER app

# Expose port for health checks
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import sys; sys.path.append('src/config'); from settings import validate_settings; exit(0 if not validate_settings() else 1)"

# Default command - run dynamic entrypoint (supports V1/V2)
CMD ["python", "scripts/docker_entrypoint.py"]