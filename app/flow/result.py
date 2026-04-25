from dataclasses import dataclass


@dataclass(frozen=True)
class FlowResult:
    answer: str
    sources: list[dict[str, str]]
