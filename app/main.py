from dotenv import load_dotenv

load_dotenv()

import os
from fastapi import FastAPI, File, UploadFile

import uuid
from typing import Dict
import aiohttp
import httpx
import openai
import speech_recognition as sr
from pydub import AudioSegment
from app.auth import AuthRequest, signin, signup
from app.schema import (
    User,
    UserCreate,
    TranscriptionCreate,
    Transcription,
)  # Importing the necessary modules

from supabase import create_client, Client


url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)


DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")
openai.api_key = os.environ.get("OPEN_API_KEY")

app = FastAPI()

uploaded_files: Dict[str, str] = {}


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


@app.post("/signup")
async def register_user(
    user: UserCreate,
):  # Update the endpoint to use the UserCreate Pydantic model
    response = await signup(user)
    return response


@app.post("/signin")
async def login_user(auth_request: AuthRequest):
    response = await signin(auth_request)
    return response


@app.post("/transcribe/")
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

    return {
        "file_id": file_id,
        "transcription": transcription,
    }


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

    response = await call_openai_chat_model(transcription)
    ai_response = response["choices"][0]["message"]["content"]
    ai_response = ai_response.replace("\n", "")

    supabase.table("transcriptions").insert(
        {"user_transcription": transcription, "ai_response": ai_response}
    ).execute()

    return {
        "file_id": file_id,
        "transcription": transcription,
        "ai_response": ai_response,
    }


@app.get("/transcriptions")
async def get_all_transcriptions():
    transcriptions = supabase.table("transcriptions").select("*").execute()
    return transcriptions


@app.get("/users")
async def get_all_users():
    users = supabase.table("users").select("*").execute()
    return users
