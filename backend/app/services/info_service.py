from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import InfoUpdate, PasswordUpdate
import app.services.user_service as user_service


def get_my_info(current_user: User) -> User:
    return current_user


def update_my_info(db: Session, user_id: int, info_in: InfoUpdate) -> User | None:
    return user_service.update_info(db, user_id, info_in)


def change_my_password(db: Session, user_id: int, password_in: PasswordUpdate) -> User | None:
    return user_service.change_password(db, user_id, password_in)
