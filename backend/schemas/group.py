from datetime import datetime
from pydantic import BaseModel


class GroupModelEntry(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_id: int
    weight: int = 1


class GroupCreate(BaseModel):
    name: str
    description: str | None = None
    polling_order: str = "sequential"


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    polling_order: str | None = None


class GroupModelAdd(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_id: int
    weight: int = 1


class GroupModelUpdateWeight(BaseModel):
    weight: int


class GroupModelResponse(BaseModel):
    model_config = {"from_attributes": True, "protected_namespaces": ()}

    model_id: int
    model_name: str
    model_model_id: str
    weight: int


class GroupResponse(BaseModel):
    model_config = {"from_attributes": True, "protected_namespaces": ()}

    id: int
    name: str
    description: str | None
    is_default: bool
    polling_order: str
    created_at: datetime
    models: list[GroupModelResponse] = []
