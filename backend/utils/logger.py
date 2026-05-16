import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.log import Log

logger = logging.getLogger("omnirouter")


async def write_log(
    db: AsyncSession,
    level: str,
    event: str,
    message: str,
    model_id: int | None = None,
    group_id: int | None = None,
    detail: str | None = None,
):
    entry = Log(
        timestamp=datetime.now(timezone.utc),
        level=level,
        event=event,
        model_id=model_id,
        group_id=group_id,
        message=message,
        detail=detail,
    )
    db.add(entry)
    await db.commit()
    logger.log(
        getattr(logging, level.upper(), logging.INFO),
        "[%s] %s",
        event,
        message,
    )
