from contextlib import asynccontextmanager
import logging
import json
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import models  # noqa: F401
from app.core.bootstrap import ensure_bootstrap_admin
import asyncio
from app.core.database import Base, engine
from app.core.config import settings
from app.routers import auth, chat, extended_profile, goal, health, profile, user
from app.routers import ws as ws_router
from app.core import ws_manager


error_logger = logging.getLogger("ai_mentor.errors")
if not error_logger.handlers:
    error_log_dir = Path(__file__).resolve().parents[1] / "logs"
    error_log_dir.mkdir(parents=True, exist_ok=True)
    error_log_path = error_log_dir / "error.log"

    error_handler = RotatingFileHandler(
        error_log_path,
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    error_logger.addHandler(error_handler)
    error_logger.setLevel(logging.INFO)
    error_logger.propagate = False


def _normalized_allowed_origins() -> list[str]:
    raw_origins = settings.ALLOWED_ORIGINS
    if isinstance(raw_origins, list):
        return [origin for origin in raw_origins if origin]

    if isinstance(raw_origins, str):
        text = raw_origins.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                loaded = json.loads(text)
                if isinstance(loaded, list):
                    return [str(origin) for origin in loaded if origin]
            except Exception:
                pass
        return [text]

    return []


ALLOWED_ORIGINS = _normalized_allowed_origins()


def _cors_headers_for_origin(origin: str | None) -> dict[str, str]:
    if not origin:
        return {}

    if "*" in ALLOWED_ORIGINS:
        return {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": "true",
        }

    if origin in ALLOWED_ORIGINS:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }

    return {}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_bootstrap_admin()
    # attach main event loop to websocket manager for cross-thread scheduling
    try:
        ws_manager.manager.loop = asyncio.get_running_loop()
    except Exception:
        ws_manager.manager.loop = None
    yield

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered mentoring and growth planning platform for university students.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_5xx_responses(request: Request, call_next):
    response = await call_next(request)
    if response.status_code >= 500:
        error_logger.error(
            "5xx response status=%s method=%s path=%s origin=%s query=%s",
            response.status_code,
            request.method,
            request.url.path,
            request.headers.get("origin"),
            request.url.query,
        )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    error_logger.exception(
        "Unhandled exception method=%s path=%s origin=%s query=%s",
        request.method,
        request.url.path,
        request.headers.get("origin"),
        request.url.query,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
        headers=_cors_headers_for_origin(request.headers.get("origin")),
    )


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(user.router)
app.include_router(profile.router)
app.include_router(extended_profile.router)
app.include_router(goal.router)
app.include_router(ws_router.router)
