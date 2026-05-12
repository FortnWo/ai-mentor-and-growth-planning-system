from sqlalchemy.orm import Session

from app.models.extended_profile import UserExtendedProfile
from app.models.user import User
from app.schemas.extended_profile import ExtendedProfileExtractionResult, UserExtendedProfileUpdate
from app.schemas.user import PasswordUpdate, ProfileUpdate
import app.services.extended_profile_service as extended_profile_service
import app.services.user_service as user_service


def get_identity_profile(current_user: User) -> User:
    return current_user


def update_identity_profile(db: Session, user_id: int, profile_in: ProfileUpdate) -> User | None:
    return user_service.update_profile(db, user_id, profile_in)


def change_identity_password(db: Session, user_id: int, password_in: PasswordUpdate) -> User | None:
    return user_service.change_password(db, user_id, password_in)


def get_or_create_user_profile(db: Session, user_id: int) -> UserExtendedProfile:
    return extended_profile_service.get_or_create_profile_for_user(db, user_id)


def update_user_profile(db: Session, user_id: int, profile_in: UserExtendedProfileUpdate) -> UserExtendedProfile:
    return extended_profile_service.update_profile_for_user(db, user_id, profile_in)


def refresh_user_profile_from_chat(
    db: Session,
    user_id: int,
) -> tuple[UserExtendedProfile, ExtendedProfileExtractionResult]:
    return extended_profile_service.refresh_profile_from_chat_history(db, user_id)


def get_user_profile_context(db: Session, user_id: int) -> UserExtendedProfile | None:
    return extended_profile_service.get_profile_for_user(db, user_id)


def list_recent_messages_for_session(db: Session, session_id: int, limit: int):
    return extended_profile_service.list_recent_messages_for_session(db, session_id, limit)


def build_profile_extraction_input(messages) -> str:
    return extended_profile_service.build_extraction_input(messages)


def parse_profile_extraction_result(raw_text: str) -> ExtendedProfileExtractionResult:
    return extended_profile_service.parse_extraction_result(raw_text)


def apply_profile_extraction_result(
    db: Session,
    user_id: int,
    result: ExtendedProfileExtractionResult,
) -> UserExtendedProfile:
    return extended_profile_service.apply_extraction_result_for_user(db, user_id, result)

