from __future__ import annotations

import json

from .engine import Cast


def write(cast: Cast) -> str:
    lines = [json.dumps(cast.header, ensure_ascii=False)]
    for event in cast.events:
        lines.append(
            json.dumps([event.interval, event.code, event.data], ensure_ascii=False)
        )
    return "\n".join(lines) + "\n"
