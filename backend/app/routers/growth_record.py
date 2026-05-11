from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.growth_record import GrowthRecordCreate, GrowthRecordRead, GrowthRecordListItem, GrowthRecordStats
from app.services import growth_record_service
from app.schemas.growth_summary import GrowthSummaryCreate, GrowthSummaryRead
from app.services import growth_summary_service

router = APIRouter(prefix="/growth-records", tags=["growth-records"])


@router.post("", response_model=GrowthRecordRead, status_code=status.HTTP_201_CREATED)
def create_record(payload: GrowthRecordCreate, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record = growth_record_service.create_growth_record(
        db,
        current_user.id,
        title=payload.title,
        summary=payload.summary,
        content=payload.content,
        record_type=payload.record_type,
        source_type=payload.source_type,
        source_ref_id=payload.source_ref_id,
        occurred_at=payload.occurred_at,
        record_date=payload.record_date,
        emotion=payload.emotion,
        score=payload.score,
        idempotency_key=payload.idempotency_key,
    )
    # schedule background summary generation (best-effort, non-blocking)
    try:
        background_tasks.add_task(growth_record_service.process_record_summary_background, record.id)
    except Exception:
        pass
    return GrowthRecordRead.model_validate(record)


@router.get("", response_model=list[GrowthRecordListItem])
def list_records(
    limit: int = 20,
    offset: int = 0,
    start_date: str | None = None,
    end_date: str | None = None,
    record_type: str | None = None,
    source_type: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total, items = growth_record_service.list_growth_records(
        db,
        current_user.id,
        limit=limit,
        offset=offset,
        start_date=start_date,
        end_date=end_date,
        record_type=record_type,
        source_type=source_type,
    )
    return [GrowthRecordListItem.model_validate(i) for i in items]


@router.get("/stats", response_model=GrowthRecordStats)
def stats(start_date: str | None = None, end_date: str | None = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = growth_record_service.stats_for_user(db, current_user.id, start_date=start_date, end_date=end_date)
    return GrowthRecordStats.model_validate(data)



@router.post("/summary/generate", response_model=GrowthSummaryRead, status_code=status.HTTP_202_ACCEPTED)
def generate_weekly_summary(payload: GrowthSummaryCreate, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # schedule background generation to avoid blocking
    try:
        def _worker(u_id: int, s, e):
            import app.core.database as database_module
            db_local = database_module.SessionLocal()
            try:
                growth_summary_service.create_weekly_summary(db_local, u_id, s, e)
            finally:
                db_local.close()

        background_tasks.add_task(_worker, current_user.id, payload.start_date, payload.end_date)
    except Exception:
        pass

    # Return accepted with a lightweight placeholder object
    return GrowthSummaryRead(id=0, user_id=current_user.id, start_date=payload.start_date, end_date=payload.end_date, summary=None, created_at=None)


@router.get("/{record_id}", response_model=GrowthRecordRead)
def get_record(record_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record = growth_record_service.get_growth_record(db, current_user.id, record_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Growth record not found")
    return GrowthRecordRead.model_validate(record)
