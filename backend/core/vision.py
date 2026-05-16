from backend.schemas.openai import ChatCompletionRequest


def request_has_images(request: ChatCompletionRequest) -> bool:
    for msg in request.messages:
        if not isinstance(msg.content, list):
            continue
        for part in msg.content:
            if isinstance(part, dict) and part.get("type") == "image_url":
                return True
    return False
