import json
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import select
from backend.database import async_session
from backend.models.setting import Setting


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/docs") or request.url.path.startswith("/openapi"):
            return await call_next(request)

        if request.url.path == "/api/auth/hint":
            return await call_next(request)

        if not (
            request.url.path.startswith("/v1/")
            or request.url.path.startswith("/api/")
        ):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

        async with async_session() as db:
            result = await db.execute(
                select(Setting).where(Setting.key == "router_api_keys")
            )
            setting = result.scalar_one_or_none()

        if not setting or not setting.value or setting.value == "[]":
            return await call_next(request)

        valid_keys: list[str] = json.loads(setting.value)
        if not valid_keys:
            return await call_next(request)

        if token not in valid_keys:
            return JSONResponse(
                status_code=401,
                content={"error": {"message": "Invalid API key", "type": "auth_error"}},
            )

        return await call_next(request)
