from __future__ import annotations

import random
from dataclasses import dataclass

from .models import Demo

LINE_STREAM_INTERVAL = 0.08


@dataclass
class Event:
    interval: float
    code: str
    data: str


@dataclass
class Cast:
    header: dict
    events: list[Event]


def _crlf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


def render(demo: Demo) -> Cast:
    meta = demo.meta
    rng = random.Random(meta.seed)
    events: list[Event] = []
    state = {"pending": 0.0, "first": True}
    base = 1.0 / meta.typing.cps

    def wait(dt: float) -> None:
        state["pending"] += max(0.0, dt)

    def emit(code: str, data: str) -> None:
        interval = 0.0 if state["first"] else round(state["pending"], 3)
        events.append(Event(interval, code, data))
        state["pending"] = 0.0
        state["first"] = False

    def char_interval() -> float:
        jitter = meta.typing.jitter
        return max(0.0, base * (1.0 + rng.uniform(-jitter, jitter)))

    for i, scene in enumerate(demo.scenes):
        if i > 0:
            wait(meta.pauses.between_scenes)
        prompt_tmpl = scene.prompt or meta.prompt
        scope = {**demo.vars, **scene.vars}
        if meta.auto_markers:
            emit("m", scene.name)
        for step in scene.steps:
            if step.type is not None:
                emit("o", prompt_tmpl.format(**scope))
                for ch in step.type:
                    wait(char_interval())
                    emit("o", ch)
                wait(char_interval())
                emit("o", "\r\n")
                wait(meta.pauses.after_command)
            elif step.output is not None:
                if step.delay:
                    wait(step.delay)
                if step.stream == "lines":
                    for j, line in enumerate(step.output.splitlines()):
                        if j > 0:
                            wait(LINE_STREAM_INTERVAL)
                        emit("o", _crlf(line) + "\r\n")
                elif step.stream == "chars":
                    for ch in _crlf(step.output):
                        wait(char_interval())
                        emit("o", ch)
                else:
                    emit("o", _crlf(step.output))
            elif step.pause is not None:
                wait(step.pause)
            elif step.banner is not None:
                emit("o", _crlf(step.banner) + "\r\n")
            elif step.clear:
                emit("o", "\x1b[2J\x1b[H")
            elif step.marker is not None:
                emit("m", step.marker)

    term: dict[str, object] = {"cols": meta.term.cols, "rows": meta.term.rows}
    if meta.term.type:
        term["type"] = meta.term.type
    header: dict[str, object] = {"version": 3, "term": term}
    if meta.title is not None:
        header["title"] = meta.title
    if meta.idle_time_limit is not None:
        header["idle_time_limit"] = meta.idle_time_limit
    return Cast(header, events)
