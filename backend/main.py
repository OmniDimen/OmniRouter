import json
import secrets
import logging
import webbrowser
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import select
from backend.config import HOST, PORT
from backend.database import engine, async_session
from backend.models import Base, Group, Setting
from backend.api import providers, models, groups, settings, logs, chat

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("omnirouter")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        result = await db.execute(select(Group).where(Group.is_default == True))
        if not result.scalar_one_or_none():
            db.add(Group(name="通用", is_default=True, polling_order="sequential"))
            await db.commit()
            logger.info("Created default group '通用'")

        result = await db.execute(
            select(Setting).where(Setting.key == "router_api_keys")
        )
        setting = result.scalar_one_or_none()
        key_file = Path(__file__).resolve().parent.parent / "data" / "api_key.txt"
        key_file.parent.mkdir(parents=True, exist_ok=True)
        if not setting or not setting.value or setting.value == "[]":
            key = "sk-" + secrets.token_hex(24)
            if setting:
                setting.value = json.dumps([key])
            else:
                db.add(Setting(key="router_api_keys", value=json.dumps([key])))
            await db.commit()
            key_file.write_text(key, encoding="utf-8")
            logger.warning("=" * 60)
            logger.warning("Auto-generated API Key:")
            logger.warning("  %s", key)
            logger.warning("Key saved to: %s", key_file)
            logger.warning("=" * 60)
        else:
            keys = json.loads(setting.value)
            if keys:
                key_file.write_text(keys[0], encoding="utf-8")

        from backend.api.logs import cleanup_old_logs
        await cleanup_old_logs(db)

    webbrowser.open(f"http://127.0.0.1:{PORT}")
    yield
    await engine.dispose()


app = FastAPI(title="OmniRouter", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(providers.router)
app.include_router(models.router)
app.include_router(groups.router)
app.include_router(settings.router)
app.include_router(logs.router)


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/")
async def root():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/index.html")
async def index_html():
    return FileResponse(FRONTEND_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=True)
