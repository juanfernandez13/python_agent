from pydantic import BaseModel

from app.api.source_item import SourceItem


class MessageResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
