from dotenv import load_dotenv

load_dotenv()

import os
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile

import uuid
from typing import Dict, List
import aiohttp
import httpx
import openai
import speech_recognition as sr
from pydub import AudioSegment
from app.auth import AuthRequest, get_current_user, signin, signup
from app.schema import (
    UserCreate,
)  # Importing the necessary modules

from supabase import create_client, Client


url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)


DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")
openai.api_key = os.environ.get("OPEN_API_KEY")

app = FastAPI()

uploaded_files: Dict[str, str] = {}


async def call_openai_chat_model(prompt: str):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a sarcastic assistant."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=140,
        n=1,
        stop=None,
        temperature=0.5,
    )
    return response


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
    return {"message": "Welcome to the transcription APII"}


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


@app.get("/auth")
async def auth_route(current_user_id: str = Depends(get_current_user)):
    user = await get_user_by_id(current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user": user}


@app.get("/user/{user_id}")
async def get_user_by_id(user_id: str):
    user = supabase.table("users").select("*").eq("id", user_id).execute()
    if user:
        return user
    else:
        raise HTTPException(status_code=404, detail="User not found")


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
async def test_upload(audio: UploadFile = File(...), user_id: str = Form(...)):
    # async def test_upload(audio_file: UploadFile = File(...)):
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
    tokens_used = response["usage"]["total_tokens"]
    supabase.table("transcriptions").insert(
        {
            "user_id": user_id,
            "user_transcription": transcription,
            "ai_response": ai_response,
            "tokens_used": tokens_used,
        }
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


@app.get("/transcription/{transcription_id}")
async def get_transcription_by_id(transcription_id: str):
    print(transcription_id)
    transcription = (
        supabase.table("transcriptions")
        .select("*")
        .eq("id", transcription_id)
        .execute()
    )

    if transcription:
        return transcription
    else:
        raise HTTPException(status_code=404, detail="Transcription not found")


@app.get("/transcriptions/user/{user_id}")
async def get_transcriptions_by_user_id(user_id: str):
    transcriptions = (
        supabase.table("transcriptions").select("*").eq("user_id", user_id).execute()
    )
    if transcriptions:
        return transcriptions
    else:
        raise HTTPException(
            status_code=404, detail="Transcriptions not found for the specified user"
        )
