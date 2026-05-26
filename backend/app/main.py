import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import BACKEND_DIR, ENV_FILES, settings
from app.db import Base, SessionLocal, engine
from app.db_migrate import ensure_schema
from app.services.yandex_config import yandex_config_status

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)
ensure_schema()

with SessionLocal() as db:
    yandex = yandex_config_status(db)
logger.info(
    "env_files=%s backend_dir=%s yandex_configured=%s api_key=%s folder_id=%s",
    ENV_FILES,
    BACKEND_DIR,
    yandex["configured"],
    yandex["api_key_configured"],
    yandex["folder_id_configured"],
)

app.include_router(router)
