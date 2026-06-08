from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class Term(BaseModel):
    model_config = {"extra": "forbid"}
    cols: int = 100
    rows: int = 30
    type: Optional[str] = "xterm-256color"


class Typing(BaseModel):
    model_config = {"extra": "forbid"}
    cps: float = 18.0
    jitter: float = 0.35


class Pauses(BaseModel):
    model_config = {"extra": "forbid"}
    after_command: float = 0.4
    between_scenes: float = 1.0


class Meta(BaseModel):
    model_config = {"extra": "forbid"}
    title: Optional[str] = None
    term: Term = Field(default_factory=Term)
    typing: Typing = Field(default_factory=Typing)
    prompt: str = "{user}@{host} {cwd} $ "
    pauses: Pauses = Field(default_factory=Pauses)
    idle_time_limit: Optional[float] = None
    seed: int = 0
    auto_markers: bool = True


class Step(BaseModel):
    model_config = {"extra": "forbid"}
    type: Optional[str] = None
    output: Optional[str] = None
    stream: Literal["instant", "lines", "chars"] = "instant"
    delay: float = 0.0
    pause: Optional[float] = None
    banner: Optional[str] = None
    clear: Optional[Literal[True]] = None
    marker: Optional[str] = None

    @model_validator(mode="after")
    def _exactly_one_action(self) -> "Step":
        actions = [
            self.type is not None,
            self.output is not None,
            self.pause is not None,
            self.banner is not None,
            self.clear is not None,
            self.marker is not None,
        ]
        if sum(actions) != 1:
            raise ValueError(
                "each step needs exactly one action: "
                "type | output | pause | banner | clear | marker"
            )
        if (self.stream != "instant" or self.delay) and self.output is None:
            raise ValueError("stream/delay are only valid with output")
        return self


class Scene(BaseModel):
    model_config = {"extra": "forbid"}
    name: str
    vars: dict[str, str] = Field(default_factory=dict)
    prompt: Optional[str] = None
    steps: list[Step]


class Demo(BaseModel):
    model_config = {"extra": "forbid"}
    meta: Meta = Field(default_factory=Meta)
    vars: dict[str, str] = Field(default_factory=dict)
    scenes: list[Scene]
