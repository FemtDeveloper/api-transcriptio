FROM python:3.9

WORKDIR /app

# Add these lines to install ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY .env ./
COPY . .

CMD ["sh", "-c", "python -m dotenv run -- clean_audio_files.py & uvicorn app.main:app --host 0.0.0.0 --port 8000"]
