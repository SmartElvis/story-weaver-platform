FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=300 --retries=5 -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8000

# Install any new requirements from mounted volume at startup, then run uvicorn
CMD ["sh", "-c", "pip install -q -r /app/requirements.txt 2>/dev/null; exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
