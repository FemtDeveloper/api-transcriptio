from dotenv import load_dotenv

load_dotenv()
from fastapi import HTTPException
import json
import os
from supabase import create_client, Client


from pydantic import BaseModel


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

    # return user
    await create_user_in_users_table(user_id, auth_request.email, auth_request.username)

    return {"message": "User registered successfully", "user": user}


async def signin(auth_request: AuthRequest):
    try:
        user, error = await supabase.auth.sign_in_with_password(
            {"email": auth_request.email, "password": auth_request.password}
        )
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": "User signed in successfully", "user": user}


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
