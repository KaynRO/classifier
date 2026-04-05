FROM python:3.11-slim

# Install Chrome, Xvfb, and system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg2 ca-certificates \
    xvfb xauth \
    libgconf-2-4 libnss3 libxss1 libasound2t64 libatk-bridge2.0-0 \
    libgtk-3-0 libdrm2 libgbm1 \
    gcc libpq-dev \
    fonts-liberation libappindicator3-1 \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install backend requirements (same as web container) + classifier deps
COPY ../backend/requirements.txt /app/backend-requirements.txt
RUN pip install --no-cache-dir -r /app/backend-requirements.txt

# Install classifier-specific deps
RUN pip install --no-cache-dir \
    seleniumbase>=4.46.0 \
    2captcha-python \
    dnspython \
    beautifulsoup4 \
    lxml \
    colorama \
    psutil

# Copy backend app code
COPY ../backend/app /app/app
COPY ../backend/alembic /app/alembic
COPY ../backend/alembic.ini /app/alembic.ini

# Copy entrypoint
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Classifier code is mounted as volume at /app/classifier
ENV CLASSIFIER_ROOT=/app/classifier
ENV PYTHONPATH=/app:/app/classifier

ENTRYPOINT ["/app/entrypoint.sh"]
