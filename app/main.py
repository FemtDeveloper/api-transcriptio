import random
from dotenv import load_dotenv

from fastapi import (
    Body,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import RedirectResponse
from typing import Dict, List, Optional
import os
import uuid
import aiohttp
import openai
from time import time
import pinecone

from app.models import TextChat, TranscriptionData, UserWithAvatar
from app.utils import (
    delete_previous_files,
    gpt3_completion,
    gpt3_embedding,
    load_conversation,
    open_file,
    timestamp_to_datetime,
)

load_dotenv()


from app.auth import AuthRequest, get_current_user, signin, signup
from app.schema import (
    UserCreate,
)

from supabase import create_client, Client


url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)


DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")
openai.api_key = os.environ.get("OPEN_API_KEY")
pinecone.init(
    api_key=os.environ.get("PINECONE_API_KEY"),
    environment=os.environ.get("PINECONE_ENVIRONMENT"),
)
vdb = pinecone.Index("spikin-database")

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


@app.get("/favicon.ico")
def read_favicon():
    return RedirectResponse(url="https://www.ionos.com/favicon.ico")


@app.get("/images/icons/{file_name}")
def read_icon(file_name: str):
    return RedirectResponse(
        url=f"https://cdn.pixabay.com/photo/2015/04/23/22/00/tree-736885_1280.jpg"
    )


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


@app.post("/user/update/")
async def update_user(request: Request):
    form = await request.form()
    print(form)

    user_data = UserWithAvatar(
        id=form["id"],
        user_name=form["name"],
        assistant_name=form["assistant_name"],
        gender=form["gender"],
        age=form["age"],
        phone_number=form["phone_number"],
        nationality=form["nationality"],
        avatar_url=form["avatar_url"],
    )

    try:
        response = (
            supabase.table("users")
            .update(user_data.dict(exclude_none=True))  # exclude None values
            .eq("id", form["id"])
            .execute()
        )
        if "error" in response:
            raise HTTPException(status_code=400, detail=response["error"])
        return {
            "message": "User data updated successfully",
            "user_id": user_data.id,
            "updated_data": user_data,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/transcribe/")
async def upload_audio(
    audio: UploadFile = File(...), user_id: str = Body(...), topic: Optional[str] = None
):
    file_id = str(uuid.uuid4())
    file_location = f"audio_files/{file_id}.wav"
    if not os.path.exists("audio_files"):
        os.makedirs("audio_files")
    delete_previous_files("audio_files")
    delete_previous_files("gpt3_logs")
    # Save the uploaded file
    with open(file_location, "wb") as f:
        f.write(audio.file.read())
    # Transcribe the audio file using Deepgram API
    transcription = await transcribe_audio_with_deepgram(file_location)
    res = (
        supabase.table("transcriptions")
        .insert({"transcription": transcription, "user_id": user_id, "topic": topic})
        .execute()
    )

    print(res)
    if res.data:
        inserted_data = res.data[0]  # Fetch the first (and only) record inserted
        return {
            "transcriptionId": inserted_data["id"],
            "transcription": transcription,
        }


@app.patch("/transcribe/update_topics")
async def update_topics(
    request: Request,
):
    data = await request.json()
    ids: List[str] = data["ids"]
    topic: str = data["topic"]
    try:
        for id in ids:
            response = (
                supabase.table("transcriptions")
                .update({"topic": topic})
                .eq("id", id)
                .execute()
            )
            if "error" in response:
                raise HTTPException(status_code=400, detail=response["error"])
        return {"message": "Topics updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/transcriptions_by_topic/")
async def get_transcriptions(user_id: str, topic: str):
    try:
        response = (
            supabase.table("transcriptions")
            .select(
                "id, transcription, topic"
            )  # select only id, transcription, and topic fields
            .eq("user_id", user_id)
            .eq("topic", topic)
            .execute()
        )
        if "error" in response:
            raise HTTPException(status_code=400, detail=response["error"])

        # Map the response data to your model
        transcriptions = [TranscriptionData(**data) for data in response.data]

        return transcriptions

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/user_topics/")
async def get_user_topics(user_id: str):
    try:
        response = (
            supabase.table("transcriptions")
            .select("topic")
            .eq("user_id", user_id)
            .execute()
        )
        if "error" in response:
            raise HTTPException(status_code=400, detail=response["error"])

        # Get the unique topics
        topics = list(
            set([data["topic"] for data in response.data if data["topic"] is not None])
        )

        return topics

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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


convo_length = 5


@app.post("/pinecone_chat/")
async def pinecone_chat(
    audio: UploadFile = File(...), user_id: str = Body(...), user_name: str = Body(...)
):
    print(user_name)
    file_id = str(uuid.uuid4())
    file_location = f"audio_files/{file_id}.wav"
    if not os.path.exists("audio_files"):
        os.makedirs("audio_files")
    delete_previous_files("audio_files")
    delete_previous_files("gpt3_logs")

    # Save the uploaded file
    with open(file_location, "wb") as f:
        f.write(audio.file.read())
    payload = list()
    transcription = await transcribe_audio_with_deepgram(file_location)
    timestamp = time()
    timestring = timestamp_to_datetime(timestamp)
    a = "\n\n%s: " % user_name + transcription
    message = transcription
    # vector : embeddding of the message, we take it and we wait with him, the message is what we send
    vector = gpt3_embedding(message)
    unique_id = str(uuid.uuid4())
    metadata = {
        "speaker": user_name,
        "time": timestamp,
        "message": message,
        "timestring": timestring,
        "uuid": unique_id,
        "user_id": user_id,
    }
    supabase.table("messages_metadata").insert(
        {
            "message": metadata["message"],
            "timestring": metadata["timestring"],
            "uuid": metadata["uuid"],
            "speaker": metadata["speaker"],
            "user_id": metadata["user_id"],
        }
    ).execute()
    topic_chars = (
        supabase.table("users")
        .select("interests", "ai_role", "assistant_name")
        .eq("id", user_id)
        .execute()
    )
    print(topic_chars)
    for user in topic_chars.data:
        interests = user["interests"]
        ai_role = user["ai_role"]
        assistant_name = user["assistant_name"]

    payload.append((unique_id, vector))
    results = vdb.query(vector=vector, top_k=convo_length)
    conversation = load_conversation(results)
    prompt = (
        open_file("prompt_response.txt")
        .replace("<<CONVERSATION>>", conversation)
        .replace("<<USER>>", user_name)
        .replace("<<MESSAGE>>", a)
        .replace("<<assistant_name>>", assistant_name)
        .replace("<<ai_role>>", ai_role)
        .replace("<<topic>>", random.choice(interests))
    )

    output = gpt3_completion(prompt)
    timestamp = time()
    timestring = timestamp_to_datetime(timestamp)
    message = output
    vector = gpt3_embedding(message)
    unique_id = str(uuid.uuid4())
    metadata = {
        "speaker": assistant_name,
        "time": timestamp,
        "message": message,
        "timestring": timestring,
        "uuid": unique_id,
        "user_id": metadata["user_id"],
    }
    supabase.table("messages_metadata").insert(
        {
            "message": metadata["message"],
            "timestring": metadata["timestring"],
            "uuid": metadata["uuid"],
            "speaker": metadata["speaker"],
            "user_id": metadata["user_id"],
        }
    ).execute()
    payload.append((unique_id, vector))
    vdb.upsert(payload)
    return {
        "output": output,
        "prompt": prompt,
        "transcription": transcription,
        "interests": interests,
    }


@app.post("/text_chat/")
async def text_chat(chat: TextChat):
    print(chat.user_name)

    delete_previous_files("gpt3_logs")

    payload = list()
    timestamp = time()
    timestring = timestamp_to_datetime(timestamp)
    a = "\n\n%s: " % chat.user_name + chat.message
    vector = gpt3_embedding(chat.message)
    unique_id = str(uuid.uuid4())
    metadata = {
        "speaker": chat.user_name,
        "time": timestamp,
        "message": chat.message,
        "timestring": timestring,
        "uuid": unique_id,
        "user_id": chat.user_id,
    }
    supabase.table("messages_metadata").insert(
        {
            "message": metadata["message"],
            "timestring": metadata["timestring"],
            "uuid": metadata["uuid"],
            "speaker": metadata["speaker"],
            "user_id": metadata["user_id"],
        }
    ).execute()

    topic_chars = (
        supabase.table("users")
        .select("interests", "ai_role", "assistant_name")
        .eq("id", chat.user_id)
        .execute()
    )
    print(topic_chars)
    for user in topic_chars.data:
        interests = user["interests"]
        ai_role = user["ai_role"]
        assistant_name = user["assistant_name"]

    payload.append((unique_id, vector))
    results = vdb.query(vector=vector, top_k=convo_length)
    conversation = load_conversation(results)
    prompt = (
        open_file("prompt_response.txt")
        .replace("<<CONVERSATION>>", conversation)
        .replace("<<USER>>", chat.user_name)
        .replace("<<MESSAGE>>", a)
        .replace("<<assistant_name>>", assistant_name)
        .replace("<<ai_role>>", ai_role)
        .replace("<<topic>>", random.choice(interests))
    )

    output = gpt3_completion(prompt)
    timestamp = time()
    timestring = timestamp_to_datetime(timestamp)
    # message = '%s: %s - %s' % ('RAVEN', timestring, output)
    message = output
    vector = gpt3_embedding(message)
    unique_id = str(uuid.uuid4())
    metadata = {
        "speaker": assistant_name,
        "time": timestamp,
        "message": message,
        "timestring": timestring,
        "uuid": unique_id,
        "user_id": metadata["user_id"],
    }
    supabase.table("messages_metadata").insert(
        {
            "message": metadata["message"],
            "timestring": metadata["timestring"],
            "uuid": metadata["uuid"],
            "speaker": metadata["speaker"],
            "user_id": metadata["user_id"],
        }
    ).execute()
    payload.append((unique_id, vector))
    vdb.upsert(payload)
    return {"output": output, "prompt": prompt, "topic_chars": topic_chars}
