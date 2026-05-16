import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.model import Model
from backend.models.group import Group
from backend.models.provider import Provider
from backend.api.settings import get_all_settings, parse_settings
from backend.schemas.openai import ChatCompletionRequest


async def route_request(
    request: ChatCompletionRequest, db: AsyncSession
) -> int | None:
    """Call the routing model to determine which group to use.
    Returns group_id or None on failure.
    """
    settings = parse_settings(await get_all_settings(db))
    if not settings.routing_model_id:
        return None

    routing_model = await db.get(Model, settings.routing_model_id)
    if not routing_model:
        return None
    provider = await db.get(Provider, routing_model.provider_id)
    if not provider or not provider.enabled:
        return None

    groups = (await db.execute(select(Group).order_by(Group.id))).scalars().all()
    if not groups:
        return None

    group_descriptions = []
    for g in groups:
        line = f'- 分组名: "{g.name}"'
        if g.description:
            line += f"，备注: \"{g.description}\""
        group_descriptions.append(line)

    context_turns = settings.routing_context_turns
    recent_messages = request.messages[-context_turns * 2:] if context_turns > 0 else request.messages[-2:]

    user_context = ""
    for msg in recent_messages:
        role = msg.role
        text = msg.content if isinstance(msg.content, str) else str(msg.content)
        user_context += f"{role}: {text}\n"

    prompt = (
        "你是一个请求路由器。根据用户的对话内容，判断应该使用哪个模型分组来处理这个请求。\n\n"
        "可用的分组：\n"
        + "\n".join(group_descriptions)
        + "\n\n请只回复分组名称，不要回复其他内容。\n\n"
        "用户最近的对话：\n"
        + user_context
    )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{provider.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {provider.api_key}"},
                json={
                    "model": routing_model.model_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 50,
                    "temperature": 0,
                },
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            answer = data["choices"][0]["message"]["content"].strip().strip('"')
    except Exception:
        return None

    for g in groups:
        if g.name == answer:
            return g.id
    return None
