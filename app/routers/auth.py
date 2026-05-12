from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr
from app.core.database import get_db
from app.core.security import create_access_token
from app.core.config import settings
from app.services.auth_service import create_user, authenticate_user

router = APIRouter(prefix="/auth", tags=["Auth"])

class SignupRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/signup", status_code=201)
async def signup(payload: SignupRequest, db: AsyncSession = Depends(get_db)):
    try:
        user = await create_user(db, payload.full_name, payload.email, payload.password)
        return {"message": "Account created!", "user_id": str(user.id), "email": user.email}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.post("/login")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = create_access_token(
        subject=str(user.id), role="user",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": str(user.id), "full_name": user.full_name, "email": user.email}
    }
