from dataclasses import dataclass


@dataclass(frozen=True)
class SectionMatch:
    section: str
    content: str
    score: int
