import datetime
import os
import uuid
from typing import Dict
import aiohttp
import httpx
import openai
import speech_recognition as sr
from pydub import AudioSegment
from fastapi import FastAPI, HTTPException, File, UploadFile
from databases import Database
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .schema import Base, Transcription


DEEPGRAM_API_KEY = "a720953fb3ec15bfd9f24b9d6060b970defded56"
openai.api_key = "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"

app = FastAPI()

uploaded_files: Dict[str, str] = {}

# Configure the database connection
DATABASE_URL = "postgresql://postgres:123qwerty@db:5432/data-english"

engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)

database = Database(DATABASE_URL)


# Connect to the database
@app.on_event("startup")
async def startup():
    await database.connect()


# Disconnect from the database
@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


async def call_openai_chat_model(transcription: str):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai.api_key}",
    }
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": transcription}],
        "max_tokens": 30,
        "n": 1,
        "temperature": 0.5,
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()


async def transcribe_audio_with_deepgram(file_path: str):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.deepgram.com/v1/listen",
            headers={
                "Authorization": f"Token {DEEPGRAM_API_KEY}",
                "Content-Type": "application/octet-stream",
            },
            data=open(file_path, "rb"),
            params={"punctuate": "true", "model": "nova"},
        ) as response:
            result = await response.json()
            return result["results"]["channels"][0]["alternatives"][0]["transcript"]


@app.get("/")
async def root():
    return {"message": "Welcome to the transcription API"}


@app.post("/upload_audio/")
async def upload_audio(audio: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    file_location = f"audio_files/{file_id}.wav"
    temp_location = f"audio_files/temp_{file_id}.mp3"

    if not os.path.exists("audio_files"):
        os.makedirs("audio_files")

    # Save the uploaded file temporarily
    with open(temp_location, "wb") as f:
        f.write(audio.file.read())

    # Convert the MP3 file to WAV format if necessary
    file_extension = os.path.splitext(audio.filename)[-1].lower()
    if file_extension == ".mp3":
        mp3_audio = AudioSegment.from_mp3(temp_location)
        mp3_audio.export(file_location, format="wav")
        os.remove(temp_location)  # Remove the temporary MP3 file
    else:
        os.rename(temp_location, file_location)

    uploaded_files[file_id] = file_location

    # Transcribe the audio file
    recognizer = sr.Recognizer()
    with sr.AudioFile(file_location) as source:
        audio_data = recognizer.record(source)
        transcription = recognizer.recognize_google(audio_data)

    # Store the transcription in the database
    query = Transcription.__table__.insert().values(
        file_id=file_id, transcription=transcription
    )
    await database.execute(query)

    return {"file_id": file_id, "transcription": transcription}


@app.post("/test_upload/")
async def test_upload(audio: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    file_location = f"audio_files/{file_id}.wav"
    if not os.path.exists("audio_files"):
        os.makedirs("audio_files")

    # Save the uploaded file
    with open(file_location, "wb") as f:
        f.write(audio.file.read())
    # Transcribe the audio file using Deepgram API
    transcription = await transcribe_audio_with_deepgram(file_location)

    print(transcription)

    response = await call_openai_chat_model(transcription)
    ai_response = response["choices"][0]["message"]["content"]
    ai_response = ai_response.replace("\n", "")

    # Store the transcription and the file_id in the database
    query = Transcription.__table__.insert().values(
        user_id=None,
        user_transcription=transcription,
        ai_response=ai_response,
        timestamp=datetime.datetime.utcnow(),
    )

    await database.execute(query)

    return {
        "file_id": file_id,
        "transcription": transcription,
        "ai_response": ai_response,
    }


@app.get("/transcribe/{file_id}")
async def transcribe(file_id: str):
    if file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="File not found")

    file_location = uploaded_files[file_id]

    # Transcribe the audio file
    recognizer = sr.Recognizer()
    with sr.AudioFile(file_location) as source:
        audio_data = recognizer.record(source)
        transcription = recognizer.recognize_google(audio_data)

    # Store the transcription in the database
    query = Transcription.__table__.insert().values(
        user_id=None,
        user_transcription=transcription,
        ai_response=None,
        timestamp=datetime.datetime.utcnow(),
    )
    await database.execute(query)

    return {"file_id": file_id, "transcription": transcription}


@app.get("/next_file/{file_id}")
async def next_file(file_id: str):
    file_ids = list(uploaded_files.keys())
    try:
        current_index = file_ids.index(file_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="File not found")

    if current_index + 1 >= len(file_ids):
        raise HTTPException(status_code=404, detail="No next file available")

    next_file_id = file_ids[current_index + 1]
    return {"file_id": next_file_id}


@app.get("/transcriptions")
async def get_all_transcriptions():
    query = Transcription.__table__.select()
    results = await database.fetch_all(query)
    return results
