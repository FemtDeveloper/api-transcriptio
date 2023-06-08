from typing import List, Optional
from pydantic import BaseModel


class UserData(BaseModel):
    id: str
    user_name: Optional[str] = None
    assistant_name: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[str] = None
    nationality: Optional[str] = None
    phone_number: Optional[str] = None
    ai_role: Optional[str] = None
    interests: Optional[List[str]] = None
    usage_time: Optional[str] = None


class TranscriptionData(BaseModel):
    id: str
    transcription: str
    topic: str


class UserWithAvatar(BaseModel):
    id: str
    user_name: Optional[str]
    assistant_name: Optional[str]
    gender: Optional[str]
    age: Optional[str]
    phone_number: Optional[str]
    country_code: Optional[str]
    nationality: Optional[str]
    avatar_url: Optional[str]
