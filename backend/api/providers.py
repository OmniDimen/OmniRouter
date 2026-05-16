from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.models.provider import Provider
from backend.models.model import Model
from backend.schemas.provider import ProviderCreate, ProviderUpdate, ProviderResponse

router = APIRouter(prefix="/api/providers", tags=["providers"])


def mask_key(key: str) -> str:
    if len(key) <= 8:
        return key[:2] + "***"
    return key[:4] + "***" + key[-4:]


def to_response(p: Provider, model_count: int = 0) -> ProviderResponse:
    return ProviderResponse(
        id=p.id,
        name=p.name,
        base_url=p.base_url,
        api_key_preview=mask_key(p.api_key),
        enabled=p.enabled,
        created_at=p.created_at,
        model_count=model_count,
    )


@router.get("", response_model=list[ProviderResponse])
async def list_providers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Provider, func.count(Model.id))
        .outerjoin(Model, Model.provider_id == Provider.id)
        .group_by(Provider.id)
        .order_by(Provider.id)
    )
    return [to_response(p, cnt) for p, cnt in result.all()]


@router.post("", response_model=ProviderResponse, status_code=201)
async def create_provider(body: ProviderCreate, db: AsyncSession = Depends(get_db)):
    p = Provider(**body.model_dump())
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return to_response(p)


@router.put("/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: int, body: ProviderUpdate, db: AsyncSession = Depends(get_db)
):
    p = await db.get(Provider, provider_id)
    if not p:
        raise HTTPException(404, "Provider not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    await db.commit()
    await db.refresh(p)
    return to_response(p)


@router.delete("/{provider_id}")
async def delete_provider(provider_id: int, db: AsyncSession = Depends(get_db)):
    p = await db.get(Provider, provider_id)
    if not p:
        raise HTTPException(404, "Provider not found")
    await db.delete(p)
    await db.commit()
    return {"ok": True}


@router.get("/{provider_id}/fetch_models")
async def fetch_remote_models(
    provider_id: int, db: AsyncSession = Depends(get_db)
):
    import httpx

    p = await db.get(Provider, provider_id)
    if not p:
        raise HTTPException(404, "Provider not found")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{p.base_url}/models",
                headers={"Authorization": f"Bearer {p.api_key}"},
            )
            if resp.status_code != 200:
                raise HTTPException(502, f"Upstream returned {resp.status_code}")
            data = resp.json()
            model_list = data.get("data", [])
            return {
                "ok": True,
                "models": [
                    {"id": m["id"], "owned_by": m.get("owned_by", "")}
                    for m in model_list
                ],
            }
    except httpx.TimeoutException:
        raise HTTPException(504, "Upstream timed out")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, str(e))
