from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.user import PasswordUpdate, ProfileUpdate, UserRead
from app.services import user_service

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/me", response_model=UserRead)
def get_my_profile(current_user=Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserRead)
def update_my_profile(
    profile_in: ProfileUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = user_service.update_profile(db, current_user.id, profile_in)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/me/password", response_model=UserRead)
def change_my_password(
    password_in: PasswordUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        user = user_service.change_password(db, current_user.id, password_in)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
