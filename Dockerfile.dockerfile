# Gunakan Python base image
FROM python:3.11-slim

# Install dependencies Chrome + lainnya
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    curl \
    gnupg \
    libnss3 \
    libgconf-2-4 \
    libxi6 \
    libgbm-dev \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxcomposite1 \
    libxrandr2 \
    libxdamage1 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    fonts-liberation \
    libappindicator3-1 \
    libxshmfence1 \
    libglu1-mesa \
    libxss1 \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome
RUN apt-get update && apt-get install -y wget gnupg2 curl \
    && curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-linux-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y google-chrome-stable

# Set Chrome path untuk webdriver-manager
ENV GOOGLE_CHROME_BIN=/usr/bin/google-chrome
ENV CHROME_DRIVER_PATH=/usr/local/bin/chromedriver

# Install pip packages
COPY requirements.txt /app/requirements.txt
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt

# Copy semua script
COPY . /app

# Command default
CMD ["python", "checkd.py"]
