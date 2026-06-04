from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.profile import ProfileInsightsRead, ProfileRefreshResponse, UserProfileRead, UserProfileUpdate
from app.services import profile_service

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/me", response_model=UserProfileRead)
def get_my_profile(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return profile_service.get_or_create_profile_for_user(db, current_user.id)


@router.get("/me/insights", response_model=ProfileInsightsRead)
def get_my_profile_insights(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return profile_service.get_profile_insights_for_user(db, current_user.id)


@router.put("/me", response_model=UserProfileRead)
def update_my_profile(
    profile_in: UserProfileUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return profile_service.update_profile_for_user(db, current_user.id, profile_in)


@router.post("/me/refresh-from-chat", response_model=ProfileRefreshResponse)
def refresh_my_profile_from_chat(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        profile, extracted = profile_service.refresh_profile_from_chat_history(db, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return ProfileRefreshResponse(profile=profile, extracted=extracted)
