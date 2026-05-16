from pydantic import BaseModel


class SettingsResponse(BaseModel):
    smart_routing_enabled: bool = False
    routing_model_id: int | None = None
    routing_context_turns: int = 3
    timeout_s: int = 60
    timeout_action: str = "error"
    auto_disable_duration_min: int = 120
    auto_disable_threshold: int = 3
    pin_model_consume_turn: bool = False
    router_api_keys: list[str] = []
    api_url: str = ""


class SettingsUpdate(BaseModel):
    smart_routing_enabled: bool | None = None
    routing_model_id: int | None = None
    routing_context_turns: int | None = None
    timeout_s: int | None = None
    timeout_action: str | None = None
    auto_disable_duration_min: int | None = None
    auto_disable_threshold: int | None = None
    pin_model_consume_turn: bool | None = None
    router_api_keys: list[str] | None = None
