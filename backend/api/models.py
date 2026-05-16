from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.models.model import Model
from backend.models.provider import Provider
from backend.schemas.model import ModelCreate, ModelUpdate, ModelResponse
from backend.core.circuit_breaker import breaker

router = APIRouter(prefix="/api/models", tags=["models"])


def to_response(m: Model, provider_name: str = "") -> ModelResponse:
    state = breaker.get_state(m.id)
    return ModelResponse(
        id=m.id,
        provider_id=m.provider_id,
        provider_name=provider_name,
        model_id=m.model_id,
        name=m.name,
        has_vision=m.has_vision,
        enabled=m.enabled,
        auto_disabled=state.disabled,
        auto_disabled_until=state.disabled_until,
        created_at=m.created_at,
    )


@router.get("", response_model=list[ModelResponse])
async def list_models(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Model, Provider.name)
        .join(Provider, Model.provider_id == Provider.id)
        .order_by(Model.id)
    )
    return [to_response(m, pname) for m, pname in result.all()]


@router.post("", response_model=ModelResponse, status_code=201)
async def create_model(body: ModelCreate, db: AsyncSession = Depends(get_db)):
    provider = await db.get(Provider, body.provider_id)
    if not provider:
        raise HTTPException(404, "Provider not found")
    conflict = await db.execute(
        select(Model).where((Model.name == body.name) | (Model.model_id == body.name))
    )
    if conflict.scalar_one_or_none():
        raise HTTPException(
            409, "Model name conflicts with an existing name or model_id"
        )
    name_as_id = await db.execute(
        select(Model).where(Model.name == body.model_id)
    )
    if name_as_id.scalar_one_or_none():
        raise HTTPException(
            409, "Model model_id conflicts with an existing model name"
        )
    m = Model(**body.model_dump())
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return to_response(m, provider.name)


@router.put("/{model_id}", response_model=ModelResponse)
async def update_model(
    model_id: int, body: ModelUpdate, db: AsyncSession = Depends(get_db)
):
    m = await db.get(Model, model_id)
    if not m:
        raise HTTPException(404, "Model not found")
    if body.name is not None and body.name != m.name:
        conflict = await db.execute(
            select(Model).where(
                (Model.id != model_id)
                & ((Model.name == body.name) | (Model.model_id == body.name))
            )
        )
        if conflict.scalar_one_or_none():
            raise HTTPException(409, "Name conflicts with existing name or model_id")
    if body.model_id is not None and body.model_id != m.model_id:
        conflict = await db.execute(
            select(Model).where(
                (Model.id != model_id) & (Model.name == body.model_id)
            )
        )
        if conflict.scalar_one_or_none():
            raise HTTPException(409, "model_id conflicts with existing model name")
    if body.provider_id is not None:
        provider = await db.get(Provider, body.provider_id)
        if not provider:
            raise HTTPException(404, "Provider not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(m, k, v)
    await db.commit()
    await db.refresh(m)
    provider = await db.get(Provider, m.provider_id)
    return to_response(m, provider.name if provider else "")


@router.delete("/{model_id}")
async def delete_model(model_id: int, db: AsyncSession = Depends(get_db)):
    m = await db.get(Model, model_id)
    if not m:
        raise HTTPException(404, "Model not found")
    await db.delete(m)
    await db.commit()
    return {"ok": True}


@router.post("/{model_id}/test")
async def test_model(model_id: int, db: AsyncSession = Depends(get_db)):
    m = await db.get(Model, model_id)
    if not m:
        raise HTTPException(404, "Model not found")
    provider = await db.get(Provider, m.provider_id)
    if not provider:
        raise HTTPException(404, "Provider not found")

    import httpx

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{provider.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {provider.api_key}"},
                json={
                    "model": m.model_id,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 5,
                },
            )
            if resp.status_code == 200:
                return {"ok": True, "message": "Model is reachable"}
            return {
                "ok": False,
                "message": f"Upstream returned {resp.status_code}",
                "detail": resp.text[:500],
            }
    except httpx.TimeoutException:
        return {"ok": False, "message": "Request timed out"}
    except Exception as e:
        return {"ok": False, "message": str(e)}
