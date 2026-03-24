from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/ping")
def ping():
    """Health-check endpoint — confirms the API is reachable."""
    return {"status": "ok", "message": "pong"}
