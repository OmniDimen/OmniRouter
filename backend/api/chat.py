import asyncio
import logging
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.models.model import Model
from backend.models.group import Group
from backend.models.group_model import GroupModel
from backend.models.provider import Provider
from backend.schemas.openai import ChatCompletionRequest
from backend.api.settings import get_all_settings, parse_settings
from backend.core.pin import resolve_pinned_model, resolve_model_field
from backend.core.vision import request_has_images
from backend.core.router import route_request
from backend.core.polling import polling_manager
from backend.core.circuit_breaker import breaker
from backend.core.forwarder import (
    forward_non_stream,
    forward_stream,
    ForwardError,
)
from backend.utils.logger import write_log

AUTO_MODEL_ID = "auto"

logger = logging.getLogger("omnirouter")
router = APIRouter()


@router.get("/v1/models")
async def list_models(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Model, Provider.name)
        .join(Provider, Model.provider_id == Provider.id)
        .where(Model.enabled == True)
        .order_by(Model.id)
    )
    models = []
    models.append({
        "id": AUTO_MODEL_ID,
        "object": "model",
        "owned_by": "omnirouter",
    })
    for m, pname in result.all():
        models.append({
            "id": m.name,
            "object": "model",
            "owned_by": pname,
        })
    return {"object": "list", "data": models}


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()
    try:
        chat_req = ChatCompletionRequest(**body)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": {"message": str(e)}})

    settings = parse_settings(await get_all_settings(db))
    has_images = request_has_images(chat_req)
    is_stream = chat_req.stream or False
    use_auto = False

    # --- Step 1: Check if model field is "auto" or empty ---
    if not chat_req.model or chat_req.model == AUTO_MODEL_ID:
        use_auto = True

    target_model: Model | None = None
    target_group_id: int | None = None

    if not use_auto:
        # --- Step 2: Check pinned model (@name) ---
        pinned_model, chat_req = await resolve_pinned_model(chat_req, db)
        if not pinned_model:
            pinned_model = await resolve_model_field(chat_req, db)

        if pinned_model:
            if not pinned_model.enabled:
                return _error_response(400, "Specified model is disabled")
            target_model = pinned_model
        else:
            use_auto = True

    if use_auto:
        # --- Step 3: Also check pin tag even in auto mode ---
        pinned_model, chat_req = await resolve_pinned_model(chat_req, db)
        if pinned_model and pinned_model.enabled:
            target_model = pinned_model
        else:
            # --- Step 4: Smart routing or default group ---
            default_group = (
                await db.execute(select(Group).where(Group.is_default == True))
            ).scalar_one_or_none()

            if not default_group:
                return _error_response(500, "No default group configured")

            if settings.smart_routing_enabled:
                routed_group_id = await route_request(chat_req, db)
                if routed_group_id:
                    target_group_id = routed_group_id
                    await write_log(
                        db, "info", "routing",
                        f"Smart routing selected group {routed_group_id}",
                        group_id=routed_group_id,
                    )
                else:
                    target_group_id = default_group.id
                    await write_log(
                        db, "warning", "routing",
                        "Smart routing failed, falling back to default group",
                        group_id=default_group.id,
                    )
            else:
                target_group_id = default_group.id

            # --- Step 5: Polling ---
            target_model = await _poll_model(
                db, target_group_id, has_images, settings
            )

    if not target_model:
        return _error_response(503, "No available model found")

    provider = await db.get(Provider, target_model.provider_id)
    if not provider or not provider.enabled:
        return _error_response(503, "Model provider is unavailable")

    # --- Step 6: Build payload (use chat_req.messages which has @tag stripped) ---
    payload = body.copy()
    payload.pop("model", None)
    payload["messages"] = [m.model_dump(exclude_none=True) for m in chat_req.messages]

    # --- Step 7: Forward ---
    if is_stream:
        return await _handle_stream(
            db, provider, target_model, payload, settings, target_group_id
        )
    else:
        return await _handle_non_stream(
            db, provider, target_model, payload, settings, target_group_id
        )


async def _poll_model(
    db: AsyncSession,
    group_id: int,
    has_images: bool,
    settings,
) -> Model | None:
    group = await db.get(Group, group_id)
    if not group:
        return None

    result = await db.execute(
        select(GroupModel).where(GroupModel.group_id == group_id)
    )
    group_models = result.scalars().all()

    active_models = []
    for gm in group_models:
        if gm.weight <= 0:
            continue
        if not breaker.is_available(gm.model_id):
            continue
        model = await db.get(Model, gm.model_id)
        if not model or not model.enabled:
            continue
        active_models.append((gm.model_id, gm.weight))

    if not active_models:
        return None

    polling_manager.ensure_queue(group_id, active_models, group.polling_order)

    max_attempts = sum(w for _, w in active_models)
    for _ in range(max_attempts):
        model_id = polling_manager.next_model(group_id)
        if model_id is None:
            return None
        model = await db.get(Model, model_id)
        if not model:
            continue
        if has_images and not model.has_vision:
            continue
        return model
    return None


async def _handle_non_stream(
    db: AsyncSession,
    provider: Provider,
    model: Model,
    payload: dict,
    settings,
    group_id: int | None,
):
    timeout_action = settings.timeout_action
    max_retries = 3 if timeout_action == "retry" else 1

    for attempt in range(max_retries):
        result = await forward_non_stream(
            provider, model, payload, settings.timeout_s
        )
        if result.success:
            breaker.record_success(model.id)
            await write_log(
                db, "info", "request",
                f"Request served by {model.name}",
                model_id=model.id,
                group_id=group_id,
            )
            return JSONResponse(content=result.body)

        if result.error == "timeout" and timeout_action == "next" and group_id:
            await write_log(
                db, "warning", "timeout",
                f"Model {model.name} timed out, trying next",
                model_id=model.id,
                group_id=group_id,
            )
            next_model = await _get_next_available_model(db, group_id, model.id, settings)
            if next_model:
                next_provider = await db.get(Provider, next_model.provider_id)
                if next_provider and next_provider.enabled:
                    result2 = await forward_non_stream(
                        next_provider, next_model, payload, settings.timeout_s
                    )
                    if result2.success:
                        breaker.record_success(next_model.id)
                        await write_log(
                            db, "info", "request",
                            f"Request served by {next_model.name} (after timeout failover)",
                            model_id=next_model.id,
                            group_id=group_id,
                        )
                        return JSONResponse(content=result2.body)

        if attempt < max_retries - 1:
            await write_log(
                db, "warning", "retry",
                f"Retrying model {model.name} (attempt {attempt + 2}/{max_retries})",
                model_id=model.id,
                group_id=group_id,
            )
            await asyncio.sleep(1)

    _record_failure(model.id, settings)
    await write_log(
        db, "error", "error",
        f"Model {model.name} failed after retries: {result.error}",
        model_id=model.id,
        group_id=group_id,
    )
    return _error_response(502, f"Upstream error: {result.error}")


async def _handle_stream(
    db: AsyncSession,
    provider: Provider,
    model: Model,
    payload: dict,
    settings,
    group_id: int | None,
):
    timeout_action = settings.timeout_action
    max_retries = 3 if timeout_action == "retry" else 1

    for attempt in range(max_retries):
        try:
            generator = forward_stream(
                provider, model, payload, settings.timeout_s
            )

            first_chunk = None
            async for chunk in generator:
                first_chunk = chunk
                break

            if first_chunk is None:
                raise ForwardError(502, "Empty response from upstream")

            async def stream_with_first():
                yield first_chunk
                async for c in generator:
                    yield c

            breaker.record_success(model.id)
            await write_log(
                db, "info", "request",
                f"Stream started by {model.name}",
                model_id=model.id,
                group_id=group_id,
            )
            return StreamingResponse(
                stream_with_first(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        except ForwardError:
            if attempt < max_retries - 1:
                await write_log(
                    db, "warning", "retry",
                    f"Stream retry model {model.name} (attempt {attempt + 2}/{max_retries})",
                    model_id=model.id,
                    group_id=group_id,
                )
                await asyncio.sleep(1)
                continue

            if timeout_action == "next" and group_id:
                await write_log(
                    db, "warning", "timeout",
                    f"Model {model.name} stream failed, trying next",
                    model_id=model.id,
                    group_id=group_id,
                )
                next_model = await _get_next_available_model(db, group_id, model.id, settings)
                if next_model:
                    next_provider = await db.get(Provider, next_model.provider_id)
                    if next_provider and next_provider.enabled:
                        try:
                            gen2 = forward_stream(
                                next_provider, next_model, payload, settings.timeout_s
                            )
                            breaker.record_success(next_model.id)
                            await write_log(
                                db, "info", "request",
                                f"Stream started by {next_model.name} (after failover)",
                                model_id=next_model.id,
                                group_id=group_id,
                            )
                            return StreamingResponse(
                                gen2,
                                media_type="text/event-stream",
                                headers={
                                    "Cache-Control": "no-cache",
                                    "Connection": "keep-alive",
                                    "X-Accel-Buffering": "no",
                                },
                            )
                        except Exception:
                            pass

            _record_failure(model.id, settings)
            await write_log(
                db, "error", "error",
                f"Model {model.name} stream failed after retries",
                model_id=model.id,
                group_id=group_id,
            )
            return _error_response(502, "Stream failed")
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
                continue
            _record_failure(model.id, settings)
            await write_log(
                db, "error", "error",
                f"Model {model.name} stream error: {e}",
                model_id=model.id,
                group_id=group_id,
            )
            return _error_response(502, f"Stream error: {e}")

    return _error_response(502, "All retries exhausted")


async def _get_next_available_model(
    db: AsyncSession, group_id: int, exclude_model_id: int, settings
) -> Model | None:
    model_id = polling_manager.next_model(group_id)
    if model_id and model_id != exclude_model_id:
        model = await db.get(Model, model_id)
        if model and model.enabled and breaker.is_available(model.id):
            return model
    return None


def _record_failure(model_id: int, settings):
    just_disabled = breaker.record_failure(
        model_id, settings.auto_disable_threshold, settings.auto_disable_duration_min
    )
    if just_disabled:
        logger.warning(
            "Model %d auto-disabled for %d minutes",
            model_id,
            settings.auto_disable_duration_min,
        )


def _error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"message": message, "type": "router_error"}},
    )
