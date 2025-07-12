FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/home/appuser/.cache/ms-playwright

# Create non-root user for security
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Install system dependencies in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Essential tools
    wget \
    curl \
    ca-certificates \
    # Playwright dependencies
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libgtk-4-1 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    xvfb \
    # Graphics libraries
    libegl1 \
    libgl1-mesa-dri \
    libgl1-mesa-glx \
    libgles2-mesa \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# Set working directory
WORKDIR /google_lens_scrapper

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright system dependencies as root first
RUN playwright install-deps chromium

# Switch to non-root user to install Playwright browsers
USER appuser

# Install Playwright browsers as the appuser (only the browser binaries)
RUN playwright install chromium

# Switch back to root to copy files and set permissions
USER root

# Copy application code
COPY --chown=appuser:appuser . .

# Create directories for data with proper permissions
RUN mkdir -p /google_lens_scrapper/data /google_lens_scrapper/logs && \
    chown -R appuser:appuser /google_lens_scrapper

# Switch to non-root user for running the application
USER appuser

# Expose port
EXPOSE 8081

# Use exec form for better signal handling
CMD ["python", "-m", "uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8081"]