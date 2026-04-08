FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg2 ca-certificates \
    xvfb xauth \
    libnss3 libxss1 libasound2t64 libatk-bridge2.0-0 \
    libgtk-3-0 libdrm2 libgbm1 \
    gcc libpq-dev \
    fonts-liberation \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Backend Python deps
COPY backend/requirements.txt /app/backend-requirements.txt
RUN pip install --no-cache-dir -r /app/backend-requirements.txt

# Tesseract OCR for FortiGuard image captchas
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Classifier engine deps
RUN pip install --no-cache-dir \
    seleniumbase>=4.46.0 \
    2captcha-python \
    dnspython \
    beautifulsoup4 \
    lxml \
    colorama \
    psutil \
    playwright \
    pytesseract \
    pillow \
    numpy \
    pyotp

# Backend app code (Celery tasks, models, config)
COPY backend/app /app/app
COPY backend/alembic /app/alembic
COPY backend/alembic.ini /app/alembic.ini

# Classifier engine code
COPY engine/modules /app/classifier/modules
COPY engine/helpers /app/classifier/helpers
COPY engine/classifier.py /app/classifier/classifier.py

# Entrypoint
COPY worker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV CLASSIFIER_ROOT=/app/classifier
ENV PYTHONPATH=/app:/app/classifier

ENTRYPOINT ["/app/entrypoint.sh"]
