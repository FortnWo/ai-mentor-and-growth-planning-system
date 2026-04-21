from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401
from app.core.bootstrap import ensure_bootstrap_admin
from app.core.database import Base, engine
from app.core.config import settings
from app.routers import auth, chat, health, profile, user


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_bootstrap_admin()
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
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(user.router)
app.include_router(profile.router)
