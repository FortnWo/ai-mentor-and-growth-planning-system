from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/{user_id}", response_model=UserRead)
def get_profile(user_id: int, db: Session = Depends(get_db)):
    """Retrieve a user profile by ID."""
    user = user_service.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("", response_model=UserRead, status_code=201)
def create_profile(user_in: UserCreate, db: Session = Depends(get_db)):
    """Create a new user profile."""
    existing = user_service.get_user_by_email(db, user_in.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    return user_service.create_user(db, user_in)


@router.patch("/{user_id}", response_model=UserRead)
def update_profile(user_id: int, user_in: UserUpdate, db: Session = Depends(get_db)):
    """Update an existing user profile."""
    user = user_service.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user_service.update_user(db, user, user_in)
