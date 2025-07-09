FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROME_PATH=/usr/bin/google-chrome

# Install system dependencies and Python 3.11
RUN apt-get update && apt-get install -y \
    software-properties-common \
    curl \
    gnupg \
    wget \
    unzip \
    xvfb \
    build-essential \
    libssl-dev \
    libffi-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libncursesw5-dev \
    zlib1g-dev \
    libgdbm-dev \
    liblzma-dev \
    tk-dev \
    ca-certificates \
    && add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Install Google Chrome
RUN curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable

# Create appuser
RUN groupadd -r appuser && useradd -r -g appuser -G audio,video appuser \
    && mkdir -p /home/appuser/Downloads && \
    chown -R appuser:appuser /home/appuser

# Set up Chrome directories and permissions
RUN mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix

# Set workdir
WORKDIR /app

# Copy Python dependencies and install
COPY requirements.txt .
RUN python3.11 -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the full app and fix ownership
COPY . .
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Create necessary Chrome dirs
RUN mkdir -p /home/appuser/.config/google-chrome && \
    mkdir -p /home/appuser/.cache/google-chrome && \
    mkdir -p /home/appuser/.local/share/applications

# Expose port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start your app
CMD ["python3.11", "src/app.py"]
