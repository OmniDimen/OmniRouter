from dataclasses import dataclass
from collections.abc import AsyncIterator
import httpx
from backend.models.model import Model
from backend.models.provider import Provider


@dataclass
class ForwardResult:
    success: bool
    status_code: int = 0
    body: dict | None = None
    error: str | None = None


async def forward_non_stream(
    provider: Provider,
    model: Model,
    payload: dict,
    timeout_s: int,
) -> ForwardResult:
    payload = {**payload, "model": model.model_id, "stream": False}
    timeout = httpx.Timeout(timeout_s, connect=10)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{provider.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {provider.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if resp.status_code == 200:
                return ForwardResult(success=True, status_code=200, body=resp.json())
            return ForwardResult(
                success=False,
                status_code=resp.status_code,
                error=resp.text[:500],
            )
    except httpx.TimeoutException:
        return ForwardResult(success=False, error="timeout")
    except Exception as e:
        return ForwardResult(success=False, error=str(e))


async def forward_stream(
    provider: Provider,
    model: Model,
    payload: dict,
    timeout_s: int,
) -> AsyncIterator[str]:
    payload = {**payload, "model": model.model_id, "stream": True}
    timeout = httpx.Timeout(timeout_s, connect=10)

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            f"{provider.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {provider.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        ) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise ForwardError(resp.status_code, body.decode("utf-8", errors="replace")[:500])
            first_chunk = True
            async for line in resp.aiter_lines():
                if first_chunk:
                    first_chunk = False
                if not line.startswith("data: "):
                    continue
                yield line + "\n\n"
                if line.strip() == "data: [DONE]":
                    return


class ForwardError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Upstream error {status_code}: {detail}")
