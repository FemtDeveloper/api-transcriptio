from pydantic import BaseModel, UUID4, EmailStr
from typing import List, Optional
from datetime import datetime


class UserBase(BaseModel):
    name: Optional[str] = None
    nationality: Optional[str] = None
    age: Optional[int] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    time_spent_in_app: Optional[float] = None
    interests: Optional[List[str]] = None  # Change this line
    profile_creation_date: Optional[datetime] = None
    credits: Optional[int] = None
    assistant_name: Optional[str] = None


class UserCreate(UserBase):
    email: EmailStr
    password: str
    username: str


class User(UserBase):
    id: UUID4

    class Config:
        orm_mode = True


class TranscriptionBase(BaseModel):
    user_id: Optional[UUID4] = None
    user_transcription: Optional[str] = None
    ai_response: Optional[str] = None
    created_at: Optional[datetime] = None
    tokens_calculated: Optional[int] = None


class TranscriptionCreate(TranscriptionBase):
    pass


class Transcription(TranscriptionBase):
    id: int

    class Config:
        orm_mode = True
