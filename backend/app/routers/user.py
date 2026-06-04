from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
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
    username_like: str | None = Query(default=None, description="学号模糊搜索"),
    major: str | None = Query(default=None, description="按专业过滤"),
    year: int | None = Query(default=None, description="按入学年份过滤（即年级）"),
    is_active: bool | None = Query(default=None, description="按启用状态过滤"),
    _current_user=Depends(require_admin("user.read")),
    db: Session = Depends(get_db),
):
    return user_service.list_users(
        db,
        skip=skip,
        limit=limit,
        username_like=username_like,
        major=major,
        year=year,
        is_active=is_active,
    )


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
    try:
        user = user_service.revoke_admin_access(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    _current_user=Depends(require_admin("user.delete")),
    db: Session = Depends(get_db),
):
    try:
        deleted = user_service.delete_user(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Bulk operations ───────────────────────────────────────────────────────────

from pydantic import BaseModel as _BaseModel  # noqa: E402


class BulkResetPasswordRequest(_BaseModel):
    user_ids: list[int]
    new_password: str


class BulkResetPasswordResponse(_BaseModel):
    success_count: int
    failed_ids: list[int]


@router.post("/bulk-reset-password", response_model=BulkResetPasswordResponse)
def bulk_reset_password(
    payload: BulkResetPasswordRequest,
    _current_user=Depends(require_admin("user.update")),
    db: Session = Depends(get_db),
):
    """批量重置用户密码。"""
    if not payload.user_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_ids is required")
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password too short")

    result = user_service.bulk_reset_password(db, payload.user_ids, payload.new_password)
    return BulkResetPasswordResponse(**result)


class ImportResultResponse(_BaseModel):
    success_count: int
    failed: list[dict]


@router.post("/import", response_model=ImportResultResponse, status_code=status.HTTP_200_OK)
async def import_users(
    file: UploadFile = File(...),
    _current_user=Depends(require_admin("user.create")),
    db: Session = Depends(get_db),
):
    """从 Excel 文件批量导入学生账号。"""
    if file.content_type not in (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "application/octet-stream",
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="USER_4091: File must be an Excel spreadsheet (.xlsx)",
        )

    contents = await file.read()
    try:
        result = user_service.import_users_from_excel(db, contents)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ImportResultResponse(**result)
