from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


def get_user(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def create_user(db: Session, user_in: UserCreate) -> User:
    if get_user_by_username(db, user_in.username):
        raise ValueError("Username already registered")
    if get_user_by_email(db, user_in.email):
        raise ValueError("Email already registered")

    db_user = User(**user_in.model_dump())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user_id: int, user_in: UserUpdate) -> User | None:
    db_user = get_user(db, user_id)
    if not db_user:
        return None

    update_data = user_in.model_dump(exclude_unset=True)

    username = update_data.get("username")
    if username and username != db_user.username:
        existing = get_user_by_username(db, username)
        if existing and existing.id != db_user.id:
            raise ValueError("Username already registered")

    email = update_data.get("email")
    if email and email != db_user.email:
        existing = get_user_by_email(db, email)
        if existing and existing.id != db_user.id:
            raise ValueError("Email already registered")

    for field, value in update_data.items():
        setattr(db_user, field, value)

    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: int) -> bool:
    db_user = get_user(db, user_id)
    if not db_user:
        return False

    db.delete(db_user)
    db.commit()
    return True
