from dotenv import load_dotenv

load_dotenv()
from fastapi import HTTPException
import os
from supabase import create_client, Client

from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from pydantic import BaseModel

# Use the same secret key for encoding and decoding JWT tokens
SECRET_KEY = os.environ.get("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: str


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=400, detail="User not found")
        return user_id
    except jwt.PyJWTError:
        raise HTTPException(status_code=400, detail="Invalid token")


url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)


class AuthRequest(BaseModel):
    email: str
    password: str
    username: str = None


async def signup(auth_request: AuthRequest):
    try:
        user, error = supabase.auth.sign_up(
            {"email": auth_request.email, "password": auth_request.password}
        )
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    user_data = user[1]
    user_id = user_data.id

    await create_user_in_users_table(user_id, auth_request.email, auth_request.username)
    return {"message": "User registered successfully", "user": user}


async def signin(auth_request: AuthRequest):
    try:
        user, error = supabase.auth.sign_in_with_password(
            {"email": auth_request.email, "password": auth_request.password}
        )
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["user"]["id"]}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer", "user": user}


async def create_user_in_users_table(user_id, email, username):
    try:
        data, error = (
            await supabase.table("users")
            .insert(
                {
                    "id": user_id,
                    "email": email,
                    "user_name": username,
                }
            )
            .execute()
        )

    except Exception as e:
        print(f"Error inserting user into custom table: {e}")
    else:
        print(f"User inserted into custom table: {data}")


async def get_user_by_email(email: str):
    user = supabase.table("users").select("*").eq("email", email).execute()
    if user:
        return user[0]
    else:
        return None
