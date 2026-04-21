from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    token_response = auth_service.login(db, payload)
    if not token_response:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    return token_response


@router.get("/me", response_model=UserRead)
def read_me(current_user=Depends(get_current_user)):
    return current_user
