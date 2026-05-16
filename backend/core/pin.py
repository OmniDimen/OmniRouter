import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.model import Model
from backend.schemas.openai import ChatCompletionRequest

PIN_PATTERN = re.compile(r"^@(\S+)\s")


async def resolve_pinned_model(
    request: ChatCompletionRequest, db: AsyncSession
) -> tuple[Model | None, ChatCompletionRequest]:
    """Check for @model_name at start of last user message.
    Returns (matched_model_or_None, possibly_modified_request).
    """
    for i in range(len(request.messages) - 1, -1, -1):
        msg = request.messages[i]
        if msg.role != "user":
            continue
        text = _extract_text(msg.content)
        if text is None:
            continue
        match = PIN_PATTERN.match(text)
        if not match:
            break
        pin_name = match.group(1)
        model = await _find_model(db, pin_name)
        if not model:
            break
        new_text = text[match.end():]
        request = _replace_text(request, i, new_text)
        return model, request
    return None, request


async def resolve_model_field(
    request: ChatCompletionRequest, db: AsyncSession
) -> Model | None:
    """Check if the request's model field matches a known model."""
    if not request.model:
        return None
    return await _find_model(db, request.model)


async def _find_model(db: AsyncSession, name: str) -> Model | None:
    result = await db.execute(select(Model).where(Model.name == name))
    model = result.scalar_one_or_none()
    if model:
        return model
    result = await db.execute(select(Model).where(Model.model_id == name))
    return result.scalar_one_or_none()


def _extract_text(content) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                return part.get("text")
    return None


def _replace_text(
    request: ChatCompletionRequest, msg_index: int, new_text: str
) -> ChatCompletionRequest:
    msg = request.messages[msg_index]
    if isinstance(msg.content, str):
        msg.content = new_text
    elif isinstance(msg.content, list):
        for part in msg.content:
            if isinstance(part, dict) and part.get("type") == "text":
                part["text"] = new_text
                break
    return request
