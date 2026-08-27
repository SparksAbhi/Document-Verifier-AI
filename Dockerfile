# SENTRY — Hugging Face Spaces deployment (Docker)
FROM python:3.11-slim

# OpenCV/EasyOCR runtime libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (cached layer)
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy the application (dbconfig.py is git-ignored, so create it from
# the template — the real connection string arrives via the DATABASE_URL
# secret configured in the Space settings)
COPY . .
RUN cp backend/dbconfig.example.py backend/dbconfig.py

# model caches must live somewhere writable
ENV HOME=/tmp HF_HOME=/tmp/hf

EXPOSE 7860
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--app-dir", "backend"]
