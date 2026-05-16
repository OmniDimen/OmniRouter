from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str | list | None = None
    name: str | None = None
    tool_calls: list | None = None
    tool_call_id: str | None = None


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    stream: bool | None = False
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    stop: str | list[str] | None = None
    tools: list | None = None
    tool_choice: str | dict | None = None

    model_config = {"extra": "allow"}
