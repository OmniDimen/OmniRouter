from datetime import datetime
from pydantic import BaseModel


class ModelCreate(BaseModel):
    model_config = {"protected_namespaces": ()}

    provider_id: int
    model_id: str
    name: str
    has_vision: bool = False
    enabled: bool = True


class ModelUpdate(BaseModel):
    model_config = {"protected_namespaces": ()}

    provider_id: int | None = None
    model_id: str | None = None
    name: str | None = None
    has_vision: bool | None = None
    enabled: bool | None = None


class ModelResponse(BaseModel):
    model_config = {"from_attributes": True, "protected_namespaces": ()}

    id: int
    provider_id: int
    provider_name: str = ""
    model_id: str
    name: str
    has_vision: bool
    enabled: bool
    auto_disabled: bool = False
    auto_disabled_until: datetime | None = None
    created_at: datetime
