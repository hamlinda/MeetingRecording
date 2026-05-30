FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg portaudio19-dev gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || echo "Some packages like pyaudiowpatch may fail on Linux, ignoring for now"

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
