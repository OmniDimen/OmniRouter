from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.models.log import Log

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
async def list_logs(
    level: str | None = Query(None),
    event: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = select(Log)
    count_query = select(func.count(Log.id))
    if level:
        query = query.where(Log.level == level)
        count_query = count_query.where(Log.level == level)
    if event:
        query = query.where(Log.event == event)
        count_query = count_query.where(Log.event == event)

    total = (await db.execute(count_query)).scalar() or 0
    query = query.order_by(Log.id.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "level": log.level,
                "event": log.event,
                "model_id": log.model_id,
                "group_id": log.group_id,
                "message": log.message,
                "detail": log.detail,
            }
            for log in logs
        ],
    }


async def cleanup_old_logs(db: AsyncSession):
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    await db.execute(delete(Log).where(Log.timestamp < cutoff))
    await db.commit()
