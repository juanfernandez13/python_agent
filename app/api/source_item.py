from pydantic import BaseModel


class SourceItem(BaseModel):
    section: str
