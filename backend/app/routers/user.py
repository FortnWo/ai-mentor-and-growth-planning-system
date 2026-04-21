from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_admin
from app.schemas.user import AdminPrivilegeUpdate, UserCreate, UserRead, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("", response_model=list[UserRead])
def list_users(
    skip: int = 0,
    limit: int = 100,
    _current_user=Depends(require_admin("user.read")),
    db: Session = Depends(get_db),
):
    return user_service.list_users(db, skip=skip, limit=limit)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    _current_user=Depends(require_admin("user.create")),
    db: Session = Depends(get_db),
):
    try:
        return user_service.create_user(db, user_in)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: int,
    _current_user=Depends(require_admin("user.read")),
    db: Session = Depends(get_db),
):
    user = user_service.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.put("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    _current_user=Depends(require_admin("user.update")),
    db: Session = Depends(get_db),
):
    try:
        user = user_service.update_user(db, user_id, user_in)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/{user_id}/admin-access", response_model=UserRead)
def grant_admin_access(
    user_id: int,
    privilege_in: AdminPrivilegeUpdate,
    _current_user=Depends(require_admin("admin.grant")),
    db: Session = Depends(get_db),
):
    try:
        user = user_service.grant_admin_access(db, user_id, privilege_in)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.delete("/{user_id}/admin-access", response_model=UserRead)
def revoke_admin_access(
    user_id: int,
    _current_user=Depends(require_admin("admin.grant")),
    db: Session = Depends(get_db),
):
    user = user_service.revoke_admin_access(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    _current_user=Depends(require_admin("user.delete")),
    db: Session = Depends(get_db),
):
    deleted = user_service.delete_user(db, user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return Response(status_code=status.HTTP_204_NO_CONTENT)
