import json
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.config import LOCAL_IP, PORT
from backend.models.setting import Setting
from backend.schemas.settings import SettingsResponse, SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULTS = {
    "smart_routing_enabled": "false",
    "routing_model_id": "",
    "routing_context_turns": "3",
    "timeout_s": "60",
    "timeout_action": "error",
    "auto_disable_duration_min": "120",
    "auto_disable_threshold": "3",
    "pin_model_consume_turn": "false",
    "router_api_keys": "[]",
}

BOOL_KEYS = {"smart_routing_enabled", "pin_model_consume_turn"}
INT_KEYS = {
    "routing_model_id",
    "routing_context_turns",
    "timeout_s",
    "auto_disable_duration_min",
    "auto_disable_threshold",
}
JSON_KEYS = {"router_api_keys"}


async def get_all_settings(db: AsyncSession) -> dict[str, str]:
    result = await db.execute(select(Setting))
    rows = {s.key: s.value for s in result.scalars().all()}
    for k, v in DEFAULTS.items():
        if k not in rows:
            rows[k] = v
    return rows


def parse_settings(raw: dict[str, str]) -> SettingsResponse:
    def to_bool(v: str) -> bool:
        return v.lower() in ("true", "1", "yes")

    def to_int_or_none(v: str) -> int | None:
        if not v:
            return None
        try:
            return int(v)
        except ValueError:
            return None

    return SettingsResponse(
        smart_routing_enabled=to_bool(raw.get("smart_routing_enabled", "false")),
        routing_model_id=to_int_or_none(raw.get("routing_model_id", "")),
        routing_context_turns=int(raw.get("routing_context_turns", "3")),
        timeout_s=int(raw.get("timeout_s", "60")),
        timeout_action=raw.get("timeout_action", "error"),
        auto_disable_duration_min=int(raw.get("auto_disable_duration_min", "120")),
        auto_disable_threshold=int(raw.get("auto_disable_threshold", "3")),
        pin_model_consume_turn=to_bool(raw.get("pin_model_consume_turn", "false")),
        router_api_keys=json.loads(raw.get("router_api_keys", "[]")),
        api_url=f"http://{LOCAL_IP}:{PORT}/v1",
    )


@router.get("", response_model=SettingsResponse)
async def get_settings(db: AsyncSession = Depends(get_db)):
    raw = await get_all_settings(db)
    return parse_settings(raw)


@router.put("", response_model=SettingsResponse)
async def update_settings(body: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    updates = body.model_dump(exclude_none=True)
    for key, value in updates.items():
        if key in BOOL_KEYS:
            str_val = str(value).lower()
        elif key in JSON_KEYS:
            str_val = json.dumps(value)
        else:
            str_val = str(value)

        existing = await db.execute(select(Setting).where(Setting.key == key))
        setting = existing.scalar_one_or_none()
        if setting:
            setting.value = str_val
        else:
            db.add(Setting(key=key, value=str_val))
    await db.commit()
    raw = await get_all_settings(db)
    return parse_settings(raw)
