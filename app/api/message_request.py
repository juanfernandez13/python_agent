from pydantic import BaseModel, Field, field_validator


class MessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = Field(
        None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_\-]+$",
    )

    @field_validator("message")
    @classmethod
    def _no_blank_message(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message não pode ser vazio ou só espaços")
        return v.strip()
