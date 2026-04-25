import httpx

from app.core.logging import get_logger
from app.llm.error import LLMError
from app.llm.message import LLMMessage

logger = get_logger(__name__)


class LLMClient:
    """Cliente LLM via API HTTP compatível com OpenAI Chat Completions.

    Suporta qualquer provedor OpenAI-compatible (OpenAI, Groq, OpenRouter,
    Together, DeepSeek, xAI, Mistral, ...) pela `LLM_BASE_URL` + `LLM_API_KEY`.
    """

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        base_url: str,
        api_key: str = "",
        temperature: float = 0.2,
        max_tokens: int = 400,
        timeout: int = 30,
    ) -> None:
        self._provider: str = provider.lower().strip()
        self._model: str = model
        self._base_url: str = base_url.rstrip("/")
        self._api_key: str = api_key
        self._temperature: float = temperature
        self._max_tokens: int = max_tokens
        self._timeout: int = timeout

    async def generate(self, messages: list[LLMMessage]) -> str:
        url = f"{self._base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"http_error: {exc}") from exc

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected_response: {data!r}") from exc
