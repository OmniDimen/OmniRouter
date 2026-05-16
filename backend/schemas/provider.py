from datetime import datetime
from pydantic import BaseModel, field_validator


class ProviderCreate(BaseModel):
    name: str
    base_url: str
    api_key: str
    enabled: bool = True

    @field_validator("base_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")


class ProviderUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    enabled: bool | None = None

    @field_validator("base_url")
    @classmethod
    def strip_trailing_slash(cls, v: str | None) -> str | None:
        return v.rstrip("/") if v else v


class ProviderResponse(BaseModel):
    id: int
    name: str
    base_url: str
    api_key_preview: str
    enabled: bool
    created_at: datetime
    model_count: int = 0

    model_config = {"from_attributes": True, "protected_namespaces": ()}
