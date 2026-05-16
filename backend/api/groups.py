from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.models.group import Group
from backend.models.group_model import GroupModel
from backend.models.model import Model
from backend.schemas.group import (
    GroupCreate,
    GroupUpdate,
    GroupModelAdd,
    GroupModelUpdateWeight,
    GroupResponse,
    GroupModelResponse,
)

router = APIRouter(prefix="/api/groups", tags=["groups"])


async def build_group_response(db: AsyncSession, g: Group) -> GroupResponse:
    result = await db.execute(
        select(GroupModel, Model.name, Model.model_id)
        .join(Model, GroupModel.model_id == Model.id)
        .where(GroupModel.group_id == g.id)
        .order_by(GroupModel.id)
    )
    models = [
        GroupModelResponse(
            model_id=gm.model_id,
            model_name=mname,
            model_model_id=mid,
            weight=gm.weight,
        )
        for gm, mname, mid in result.all()
    ]
    return GroupResponse(
        id=g.id,
        name=g.name,
        description=g.description,
        is_default=g.is_default,
        polling_order=g.polling_order,
        created_at=g.created_at,
        models=models,
    )


@router.get("", response_model=list[GroupResponse])
async def list_groups(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Group).order_by(Group.id))
    groups = result.scalars().all()
    return [await build_group_response(db, g) for g in groups]


@router.post("", response_model=GroupResponse, status_code=201)
async def create_group(body: GroupCreate, db: AsyncSession = Depends(get_db)):
    if body.polling_order not in ("sequential", "random"):
        raise HTTPException(400, "polling_order must be 'sequential' or 'random'")
    g = Group(**body.model_dump())
    db.add(g)
    await db.commit()
    await db.refresh(g)
    return await build_group_response(db, g)


@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: int, body: GroupUpdate, db: AsyncSession = Depends(get_db)
):
    g = await db.get(Group, group_id)
    if not g:
        raise HTTPException(404, "Group not found")
    if body.polling_order and body.polling_order not in ("sequential", "random"):
        raise HTTPException(400, "polling_order must be 'sequential' or 'random'")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(g, k, v)
    await db.commit()
    await db.refresh(g)
    return await build_group_response(db, g)


@router.delete("/{group_id}")
async def delete_group(group_id: int, db: AsyncSession = Depends(get_db)):
    g = await db.get(Group, group_id)
    if not g:
        raise HTTPException(404, "Group not found")
    if g.is_default:
        raise HTTPException(400, "Cannot delete the default group")
    await db.delete(g)
    await db.commit()
    return {"ok": True}


@router.post("/{group_id}/models", status_code=201)
async def add_model_to_group(
    group_id: int, body: GroupModelAdd, db: AsyncSession = Depends(get_db)
):
    g = await db.get(Group, group_id)
    if not g:
        raise HTTPException(404, "Group not found")
    m = await db.get(Model, body.model_id)
    if not m:
        raise HTTPException(404, "Model not found")
    existing = await db.execute(
        select(GroupModel).where(
            (GroupModel.group_id == group_id) & (GroupModel.model_id == body.model_id)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Model already in this group")
    gm = GroupModel(group_id=group_id, model_id=body.model_id, weight=body.weight)
    db.add(gm)
    await db.commit()
    return {"ok": True}


@router.put("/{group_id}/models/{model_id}")
async def update_model_weight(
    group_id: int,
    model_id: int,
    body: GroupModelUpdateWeight,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GroupModel).where(
            (GroupModel.group_id == group_id) & (GroupModel.model_id == model_id)
        )
    )
    gm = result.scalar_one_or_none()
    if not gm:
        raise HTTPException(404, "Model not in this group")
    gm.weight = body.weight
    await db.commit()
    return {"ok": True}


@router.delete("/{group_id}/models/{model_id}")
async def remove_model_from_group(
    group_id: int, model_id: int, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(GroupModel).where(
            (GroupModel.group_id == group_id) & (GroupModel.model_id == model_id)
        )
    )
    gm = result.scalar_one_or_none()
    if not gm:
        raise HTTPException(404, "Model not in this group")
    await db.delete(gm)
    await db.commit()
    return {"ok": True}
