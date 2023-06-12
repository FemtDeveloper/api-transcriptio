from typing import List, Optional
from pydantic import BaseModel


class UserData(BaseModel):
    id: str
    age: Optional[str] = None
    ai_role: Optional[str] = None
    assistant_name: Optional[str] = None
    avatar_url: Optional[str]
    country_code: Optional[str]
    gender: Optional[str] = None
    interests: Optional[List[str]] = None
    nationality: Optional[str] = None
    phone_number: Optional[str] = None
    usage_time: Optional[str] = None
    user_name: Optional[str] = None


class TranscriptionData(BaseModel):
    id: str
    transcription: str
    topic: str


class UserWithAvatar(BaseModel):
    id: str
    age: Optional[str]
    assistant_name: Optional[str]
    avatar_url: Optional[str]
    country_code: Optional[str]
    gender: Optional[str]
    nationality: Optional[str]
    phone_number: Optional[str]
    user_name: Optional[str]


class TextChat(BaseModel):
    message: str
    user_name: str
    user_id: str
