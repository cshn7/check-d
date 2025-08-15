# Gunakan Python slim
FROM python:3.13-slim

# Set environment
ENV PYTHONUNBUFFERED=1
ENV GOOGLE_CHROME_BIN=/usr/bin/chromium

# Install Chromium dan dependencies
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    wget \
    curl \
    gnupg2 \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install pip dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app
WORKDIR /app

# Command default
CMD ["python", "checkd.py"]
