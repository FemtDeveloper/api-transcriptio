from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    nationality = Column(String)
    age = Column(Integer)
    email = Column(String)
    phone_number = Column(String)
    time_spent_in_app = Column(Float)
    interests = Column(JSON)
    profile_creation_date = Column(DateTime)
    credits = Column(Integer)
    assistant_name = Column(String)

    transcriptions = relationship("Transcription", back_populates="user")


class Transcription(Base):
    __tablename__ = "transcriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    user_transcription = Column(String)
    ai_response = Column(String)
    timestamp = Column(DateTime)
    tokens_calculated = Column(Integer)

    user = relationship("User", back_populates="transcriptions")
