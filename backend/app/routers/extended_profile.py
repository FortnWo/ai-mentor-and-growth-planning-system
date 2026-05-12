from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.extended_profile import (
    ExtendedProfileRefreshResponse,
    UserExtendedProfileRead,
    UserExtendedProfileUpdate,
)
from app.services import profile_service

router = APIRouter(prefix="/profile/extended", tags=["profile"])


@router.get("/me", response_model=UserExtendedProfileRead)
def get_my_extended_profile(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return profile_service.get_or_create_user_profile(db, current_user.id)


@router.put("/me", response_model=UserExtendedProfileRead)
def update_my_extended_profile(
    profile_in: UserExtendedProfileUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return profile_service.update_user_profile(db, current_user.id, profile_in)


@router.post("/me/refresh-from-chat", response_model=ExtendedProfileRefreshResponse)
def refresh_my_extended_profile_from_chat(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        profile, extracted = profile_service.refresh_user_profile_from_chat(db, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return ExtendedProfileRefreshResponse(profile=profile, extracted=extracted)
