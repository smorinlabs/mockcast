# mockcast Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI that renders a declarative YAML demo-script into a valid asciicast v3 `.cast` file (a scripted fake terminal session), and ship the `acme ai` hero-cut demo.

**Architecture:** Three I/O-free units behind a thin CLI: `models.py` (pydantic schema + validation) → `engine.py` (pure `Demo → Cast` renderer holding all timing/typing/marker logic) → `writer.py` (serialize to newline-delimited JSON). `cli.py` wires `render`/`validate`/`play`. Output is byte-reproducible (seeded RNG, no `timestamp`).

**Tech Stack:** Python 3.12, uv, pydantic v2, PyYAML, pytest, ruff, ty, just. asciinema ≥ 3.0 for playback (confirmed 3.2.0 installed).

**Spec:** `docs/superpowers/specs/2026-06-04-flox-ai-demo-design.md`

---

## File Structure

| File | Responsibility |
|------|----------------|
| `pyproject.toml` | uv package, deps, `mockcast` console script |
| `justfile` | `format`, `lint`, `typecheck`, `test`, `all` |
| `Makefile` | `make check` — verify uv/asciinema present |
| `src/mockcast/__init__.py` | package marker |
| `src/mockcast/models.py` | `Demo`/`Meta`/`Term`/`Typing`/`Pauses`/`Scene`/`Step` schema |
| `src/mockcast/engine.py` | `Event`, `Cast`, `render(demo) -> Cast` (pure) |
| `src/mockcast/writer.py` | `write(cast) -> str` |
| `src/mockcast/cli.py` | `main()` + `render`/`validate`/`play` |
| `tests/test_models.py` | schema validation |
| `tests/test_writer.py` | serialization golden |
| `tests/test_engine.py` | timing/markers/identity golden + determinism |
| `tests/test_cli.py` | render writes file; validate errors |
| `examples/acme-ai-day.yaml` | the 10-beat hero cut |

---

## Task 0: Project scaffold

**Files:**
- Create: `pyproject.toml`, `justfile`, `Makefile`, `src/mockcast/__init__.py`

- [ ] **Step 1: Initialize uv package**

Run:
```bash
uv init --package --name mockcast --no-readme .
```
(If `pyproject.toml` already exists from a prior step, skip. This creates `src/mockcast/__init__.py` and a `pyproject.toml`.)

- [ ] **Step 2: Add runtime and dev dependencies**

Run:
```bash
uv add pydantic pyyaml
uv add --dev pytest ruff ty
```

- [ ] **Step 3: Set the console script entry point**

Edit `pyproject.toml` to add (under `[project.scripts]`, create the table if absent):
```toml
[project.scripts]
mockcast = "mockcast.cli:main"
```
Ensure `requires-python = ">=3.12"` is set in `[project]`.

- [ ] **Step 4: Create the justfile**

Create `justfile`:
```just
default:
    @just --list

format:
    uv run ruff format .

lint:
    uv run ruff check .

typecheck:
    uv run ty check

test:
    uv run pytest -q

all: format lint typecheck test
```

- [ ] **Step 5: Create the Makefile dependency check**

Create `Makefile`:
```makefile
.PHONY: check
check:
	@command -v uv >/dev/null 2>&1 || { echo "uv not found"; exit 1; }
	@command -v asciinema >/dev/null 2>&1 || { echo "asciinema not found (need >= 3.0)"; exit 1; }
	@asciinema --version
	@echo "dependencies OK"
```

- [ ] **Step 6: Verify the toolchain**

Run: `make check`
Expected: prints `asciinema 3.x.y` then `dependencies OK`.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: scaffold mockcast uv project"
```

---

## Task 1: Schema and validation (`models.py`)

**Files:**
- Create: `src/mockcast/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_models.py`:
```python
import pytest
from pydantic import ValidationError

from mockcast.models import Demo, Step


def test_minimal_demo_validates():
    demo = Demo.model_validate(
        {"scenes": [{"name": "s", "steps": [{"type": "echo hi"}]}]}
    )
    assert demo.scenes[0].name == "s"
    assert demo.scenes[0].steps[0].type == "echo hi"
    # defaults applied
    assert demo.meta.term.cols == 100
    assert demo.meta.auto_markers is True


def test_step_requires_exactly_one_action():
    with pytest.raises(ValidationError):
        Step.model_validate({"type": "a", "pause": 1.0})
    with pytest.raises(ValidationError):
        Step.model_validate({})


def test_stream_only_valid_with_output():
    with pytest.raises(ValidationError):
        Step.model_validate({"type": "a", "stream": "lines"})
    # valid combo
    s = Step.model_validate({"output": "x", "stream": "lines"})
    assert s.stream == "lines"


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        Demo.model_validate(
            {"scenes": [{"name": "s", "steps": [{"typo": "oops"}]}]}
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'mockcast.models'`.

- [ ] **Step 3: Write the schema**

Create `src/mockcast/models.py`:
```python
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
    think: float = 0.8
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
    stream: Literal["instant", "lines"] = "instant"
    delay: float = 0.0
    pause: Optional[float] = None
    banner: Optional[str] = None
    clear: Optional[bool] = None
    marker: Optional[str] = None

    @model_validator(mode="after")
    def _exactly_one_action(self) -> "Step":
        actions = [
            self.type is not None,
            self.output is not None,
            self.pause is not None,
            self.banner is not None,
            bool(self.clear),
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mockcast/models.py tests/test_models.py
git commit -m "feat: add demo-script schema and validation"
```

---

## Task 2: Cast serializer (`writer.py`)

**Files:**
- Create: `src/mockcast/writer.py`
- Test: `tests/test_writer.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_writer.py`:
```python
import json

from mockcast.engine import Cast, Event
from mockcast.writer import write


def test_write_produces_v3_lines():
    cast = Cast(
        header={"version": 3, "term": {"cols": 80, "rows": 24}},
        events=[Event(0.0, "o", "hi\r\n"), Event(0.25, "m", "chapter")],
    )
    text = write(cast)
    lines = text.splitlines()

    assert json.loads(lines[0]) == {"version": 3, "term": {"cols": 80, "rows": 24}}
    assert json.loads(lines[1]) == [0.0, "o", "hi\r\n"]
    assert json.loads(lines[2]) == [0.25, "m", "chapter"]
    assert text.endswith("\n")


def test_write_keeps_unicode_literal_but_escapes_control():
    cast = Cast(
        header={"version": 3, "term": {"cols": 80, "rows": 24}},
        events=[Event(0.0, "o", "✔ \x1b[2J")],
    )
    text = write(cast)
    # printable unicode stays literal; ESC is escaped
    assert "✔" in text
    assert "\\u001b" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_writer.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'mockcast.writer'` (and `engine`).

- [ ] **Step 3: Write the serializer**

Create `src/mockcast/writer.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_writer.py -q`
Expected: PASS (2 tests). (`Cast`/`Event` come from `engine.py`, created next task — if running this task in isolation, it will fail at import until Task 3. Run the full suite after Task 3.)

- [ ] **Step 5: Commit**

```bash
git add src/mockcast/writer.py tests/test_writer.py
git commit -m "feat: add asciicast v3 serializer"
```

---

## Task 3: Engine — header + typing (`engine.py`)

**Files:**
- Create: `src/mockcast/engine.py`
- Test: `tests/test_engine.py`

- [ ] **Step 1: Write the failing test (deterministic, jitter=0)**

Create `tests/test_engine.py`:
```python
from mockcast.engine import render
from mockcast.models import Demo


def _demo(**meta):
    base = {
        "meta": {
            "typing": {"cps": 10, "jitter": 0},
            "pauses": {"after_command": 0.0, "between_scenes": 0.0},
            "auto_markers": False,
            "prompt": "$ ",
            **meta,
        },
        "vars": {},
        "scenes": [],
    }
    return base


def test_header_built_from_meta():
    demo = Demo.model_validate(
        {**_demo(title="t", idle_time_limit=2.0),
         "scenes": [{"name": "s", "steps": []}]}
    )
    cast = render(demo)
    assert cast.header["version"] == 3
    assert cast.header["term"]["cols"] == 100
    assert cast.header["term"]["type"] == "xterm-256color"
    assert cast.header["title"] == "t"
    assert cast.header["idle_time_limit"] == 2.0


def test_typing_emits_prompt_then_chars_then_enter():
    demo = Demo.model_validate(
        {**_demo(),
         "scenes": [{"name": "s", "steps": [{"type": "hi"}]}]}
    )
    cast = render(demo)
    events = [(e.interval, e.code, e.data) for e in cast.events]
    assert events == [
        (0.0, "o", "$ "),     # prompt, first event interval is 0.0
        (0.1, "o", "h"),      # 1/cps = 0.1
        (0.1, "o", "i"),
        (0.1, "o", "\r\n"),   # Enter
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_engine.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'mockcast.engine'`.

- [ ] **Step 3: Write the engine skeleton (header + typing)**

Create `src/mockcast/engine.py`:
```python
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

    header: dict = {
        "version": 3,
        "term": {"cols": meta.term.cols, "rows": meta.term.rows},
    }
    if meta.term.type:
        header["term"]["type"] = meta.term.type
    if meta.title is not None:
        header["title"] = meta.title
    if meta.idle_time_limit is not None:
        header["idle_time_limit"] = meta.idle_time_limit
    return Cast(header, events)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_engine.py tests/test_writer.py -q`
Expected: PASS (engine: 2, writer: 2).

- [ ] **Step 5: Commit**

```bash
git add src/mockcast/engine.py tests/test_engine.py
git commit -m "feat: add engine with header build and typing"
```

---

## Task 4: Engine — output, pause, banner, clear

**Files:**
- Modify: `src/mockcast/engine.py` (add step handling inside the scene loop)
- Test: `tests/test_engine.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_engine.py`:
```python
def test_output_instant_one_event_with_crlf():
    demo = Demo.model_validate(
        {**_demo(),
         "scenes": [{"name": "s", "steps": [{"output": "a\nb"}]}]}
    )
    cast = render(demo)
    events = [(e.interval, e.code, e.data) for e in cast.events]
    assert events == [(0.0, "o", "a\r\nb")]


def test_output_lines_streams_each_line():
    demo = Demo.model_validate(
        {**_demo(),
         "scenes": [{"name": "s",
                     "steps": [{"output": "a\nb", "stream": "lines"}]}]}
    )
    cast = render(demo)
    events = [(e.interval, e.code, e.data) for e in cast.events]
    assert events == [
        (0.0, "o", "a\r\n"),
        (0.08, "o", "b\r\n"),
    ]


def test_pause_and_delay_add_to_next_interval():
    demo = Demo.model_validate(
        {**_demo(),
         "scenes": [{"name": "s",
                     "steps": [{"pause": 1.0},
                               {"output": "x", "delay": 0.5}]}]}
    )
    cast = render(demo)
    # single event; pause(1.0)+delay(0.5) but first event interval is 0.0
    assert [(e.interval, e.code, e.data) for e in cast.events] == [(0.0, "o", "x")]


def test_banner_and_clear():
    demo = Demo.model_validate(
        {**_demo(),
         "scenes": [{"name": "s",
                     "steps": [{"clear": True}, {"banner": "--- cut ---"}]}]}
    )
    cast = render(demo)
    events = [(e.code, e.data) for e in cast.events]
    assert events == [("o", "\x1b[2J\x1b[H"), ("o", "--- cut ---\r\n")]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_engine.py -q`
Expected: FAIL — output/pause/banner/clear steps currently produce no events (assertions mismatch).

- [ ] **Step 3: Extend the scene loop**

In `src/mockcast/engine.py`, replace the inner `for step in scene.steps:` block with:
```python
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
                else:
                    emit("o", _crlf(step.output))
            elif step.pause is not None:
                wait(step.pause)
            elif step.banner is not None:
                emit("o", _crlf(step.banner) + "\r\n")
            elif step.clear:
                emit("o", "\x1b[2J\x1b[H")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_engine.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mockcast/engine.py tests/test_engine.py
git commit -m "feat: handle output, pause, banner, clear steps"
```

---

## Task 5: Engine — markers, auto-markers, identity swap, determinism

**Files:**
- Modify: `src/mockcast/engine.py` (add `marker` step in the loop)
- Test: `tests/test_engine.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_engine.py`:
```python
def test_explicit_marker_emits_m_event():
    demo = Demo.model_validate(
        {**_demo(),
         "scenes": [{"name": "s", "steps": [{"marker": "chapter one"}]}]}
    )
    cast = render(demo)
    assert [(e.code, e.data) for e in cast.events] == [("m", "chapter one")]


def test_auto_markers_emit_scene_name_at_start():
    base = _demo()
    base["meta"]["auto_markers"] = True
    demo = Demo.model_validate(
        {**base,
         "scenes": [{"name": "onboard", "steps": [{"output": "hi"}]}]}
    )
    cast = render(demo)
    assert [(e.code, e.data) for e in cast.events] == [
        ("m", "onboard"),
        ("o", "hi"),
    ]


def test_scene_vars_swap_prompt_identity():
    base = _demo(prompt="{user}@{host} $ ")
    demo = Demo.model_validate(
        {**base,
         "vars": {"user": "maya", "host": "laptop"},
         "scenes": [
             {"name": "a", "steps": [{"type": "x"}]},
             {"name": "b", "vars": {"user": "sam", "host": "ws"},
              "steps": [{"type": "y"}]},
         ]}
    )
    cast = render(demo)
    prompts = [e.data for e in cast.events if e.code == "o" and "@" in e.data]
    assert prompts == ["maya@laptop $ ", "sam@ws $ "]


def test_render_is_deterministic_with_jitter():
    spec = {
        "meta": {"typing": {"cps": 12, "jitter": 0.5}, "seed": 7},
        "scenes": [{"name": "s", "steps": [{"type": "acme ai status"}]}],
    }
    a = render(Demo.model_validate(spec))
    b = render(Demo.model_validate(spec))
    assert [(e.interval, e.code, e.data) for e in a.events] == [
        (e.interval, e.code, e.data) for e in b.events
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_engine.py -q`
Expected: FAIL on `test_explicit_marker_emits_m_event` (marker step not handled yet); identity/auto-marker/determinism may already pass.

- [ ] **Step 3: Add the marker step handler**

In `src/mockcast/engine.py`, add one more branch at the end of the `for step` chain (after the `elif step.clear:` branch):
```python
            elif step.marker is not None:
                emit("m", step.marker)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_engine.py -q`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mockcast/engine.py tests/test_engine.py
git commit -m "feat: support markers, auto-markers, identity swap"
```

---

## Task 6: CLI — `render` and `validate`

**Files:**
- Create: `src/mockcast/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli.py`:
```python
import json

import pytest

from mockcast.cli import main


def _write_demo(tmp_path):
    demo = tmp_path / "d.yaml"
    demo.write_text(
        "meta:\n"
        "  typing: {cps: 10, jitter: 0}\n"
        "  auto_markers: false\n"
        "  prompt: '$ '\n"
        "scenes:\n"
        "  - name: s\n"
        "    steps:\n"
        "      - type: hi\n"
    )
    return demo


def test_render_writes_valid_v3_file(tmp_path):
    demo = _write_demo(tmp_path)
    out = tmp_path / "out.cast"
    rc = main(["render", str(demo), "-o", str(out)])
    assert rc == 0
    lines = out.read_text().splitlines()
    assert json.loads(lines[0])["version"] == 3
    # every event line is [interval, code, data]
    for line in lines[1:]:
        interval, code, data = json.loads(line)
        assert isinstance(interval, (int, float)) and interval >= 0
        assert code in {"o", "m"}
    # first event interval is 0.0
    assert json.loads(lines[1])[0] == 0.0


def test_validate_ok(tmp_path, capsys):
    demo = _write_demo(tmp_path)
    rc = main(["validate", str(demo)])
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_validate_reports_error(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("scenes:\n  - name: s\n    steps:\n      - {}\n")
    rc = main(["validate", str(bad)])
    assert rc == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'mockcast.cli'`.

- [ ] **Step 3: Write the CLI**

Create `src/mockcast/cli.py`:
```python
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError

from .engine import render
from .models import Demo
from .writer import write


def _load(path: str) -> Demo:
    data = yaml.safe_load(Path(path).read_text())
    return Demo.model_validate(data)


def cmd_render(args: argparse.Namespace) -> int:
    cast = render(_load(args.demo))
    Path(args.output).write_text(write(cast))
    print(f"wrote {args.output} ({len(cast.events)} events)")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        _load(args.demo)
    except ValidationError as exc:
        print(exc, file=sys.stderr)
        return 1
    print("OK")
    return 0


def cmd_play(args: argparse.Namespace) -> int:
    cast = render(_load(args.demo))
    with tempfile.NamedTemporaryFile(
        "w", suffix=".cast", delete=False
    ) as handle:
        handle.write(write(cast))
        path = handle.name
    return subprocess.run(["asciinema", "play", path]).returncode


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="mockcast")
    sub = parser.add_subparsers(dest="cmd", required=True)

    render_p = sub.add_parser("render", help="render a demo to a .cast file")
    render_p.add_argument("demo")
    render_p.add_argument("-o", "--output", required=True)
    render_p.set_defaults(func=cmd_render)

    validate_p = sub.add_parser("validate", help="schema-check a demo")
    validate_p.add_argument("demo")
    validate_p.set_defaults(func=cmd_validate)

    play_p = sub.add_parser("play", help="render then asciinema play")
    play_p.add_argument("demo")
    play_p.set_defaults(func=cmd_play)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mockcast/cli.py tests/test_cli.py
git commit -m "feat: add render/validate/play CLI"
```

---

## Task 7: The hero-cut example + real-playback acceptance

**Files:**
- Create: `examples/acme-ai-day.yaml`

- [ ] **Step 1: Author the hero cut**

Create `examples/acme-ai-day.yaml`. Use the 10 beats from the spec; each scene name becomes a chapter marker (auto_markers on). Embed ANSI green checkmarks via `[32m...[0m` if desired, or keep plain. Minimum viable version:
```yaml
meta:
  title: "acme ai — a day in the life"
  term: { cols: 100, rows: 30, type: xterm-256color }
  typing: { cps: 22, jitter: 0.35 }
  prompt: "{user}@{host} {cwd} $ "
  pauses: { after_command: 0.5, think: 0.9, between_scenes: 1.2 }
  idle_time_limit: 2.0
  seed: 42
  auto_markers: true

vars: { user: maya, host: laptop, cwd: "~/acme" }

scenes:
  - name: onboard
    steps:
      - type: "acme ai profile install acme-team"
      - output: |
          Resolving acme-team…
          ✔ claude-code   installed
          ✔ codex         already up to date
          ✔ gemini-cli    installed
          ✔ synced 7 skills · logged in as maya
        stream: lines
      - pause: 1.0

  - name: verify
    steps:
      - type: "acme ai doctor"
      - output: |
          claude-code  auto-updated → 1.4.2
          codex        current
          skills       7 synced (1 drift auto-fixed)
          auth         ok
        stream: lines
      - pause: 0.8

  - name: launch
    steps:
      - type: "acme ai launch"
      - output: |
          Starting Claude Code (macOS)…
        stream: lines
      - pause: 0.6

  - name: usage
    steps:
      - type: "acme ai usage"
      - output: |
          tool          sessions   tokens
          claude-code          3   182k
          codex                1    24k
        stream: lines
      - pause: 0.8

  - name: search
    steps:
      - type: "acme ai search recipe"
      - output: |
          No skills matched “recipe”. Build one? → acme ai skill dev <name>
        stream: lines
      - pause: 0.8

  - name: author
    steps:
      - type: "acme ai skill dev recipe-helper"
      - output: |
          recipe-helper → dev mode (hot-reload watching ./skills/recipe-helper)
        stream: lines
      - type: "acme ai skill restart recipe-helper"
      - output: |
          reloaded recipe-helper ✔
        stream: lines
      - pause: 0.8

  - name: ship
    steps:
      - type: "acme ai skill sync"
      - type: "acme ai skill publish recipe-helper"
      - output: |
          published recipe-helper@0.1.0 → acme-team registry
        stream: lines
      - pause: 0.8

  - name: promote
    steps:
      - type: "acme ai skill use recipe-helper --production"
      - output: |
          recipe-helper: dev → production (active in maya’s profile)
        stream: lines
      - pause: 0.8

  - name: teammate
    vars: { user: sam, host: workstation }
    prompt: "{user}@{host} $ "
    steps:
      - banner: "─────────────  Sam's machine  ─────────────"
      - type: "acme ai search recipe"
      - output: |
          recipe-helper@0.1.0   acme-team   ★ new
        stream: lines
      - type: "acme ai profile pull"
      - output: |
          pulled acme-team · installed recipe-helper@0.1.0
        stream: lines
      - pause: 0.8

  - name: status
    vars: { user: maya, host: laptop, cwd: "~/acme" }
    steps:
      - type: "acme ai status"
      - output: |
          profile     acme-team (locked)
          tools       claude-code 1.4.2 · codex · gemini-cli
          skills      8 active  (recipe-helper@0.1.0 ✔)
          scope       user ⊕ team ⊕ project
        stream: lines
      - pause: 1.5
```

- [ ] **Step 2: Validate the example**

Run: `uv run mockcast validate examples/acme-ai-day.yaml`
Expected: `OK`.

- [ ] **Step 3: Render the example**

Run: `uv run mockcast render examples/acme-ai-day.yaml -o out.cast`
Expected: `wrote out.cast (N events)`; `out.cast` exists.

- [ ] **Step 4: Real-playback acceptance (closes the loop)**

Run: `asciinema play out.cast`
Expected: the full hero cut plays end-to-end; the prompt switches to `sam@workstation` at the banner. Then verify the markers are present:
```bash
grep -c '"m"' out.cast
```
Expected: ≥ 10 (one per scene). These render as navigable chapter points in the player. Schema validity alone is not sufficient — this playback step is the real acceptance.

- [ ] **Step 5: Commit**

```bash
git add examples/acme-ai-day.yaml
git commit -m "feat: add acme ai hero-cut demo"
```

---

## Task 8: Full verification gate

**Files:** none (verification only)

- [ ] **Step 1: Run the full quality gate**

Run: `make check && just all`
Expected: dependency check passes; ruff format clean, ruff lint clean, `ty check` clean, all pytest tests pass.

- [ ] **Step 2: Fix any lint/type findings**

If `ruff` or `ty` report issues, fix them minimally (no behavior changes) and re-run `just all` until green.

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: pass full lint/type/test gate"
```

---

## Acceptance criteria (from spec)

- `mockcast render examples/acme-ai-day.yaml -o out.cast` produces a spec-valid v3 file.
- `asciinema play out.cast` plays the hero cut end-to-end with navigable chapter markers (real playback — not just schema validity).
- `just all` passes (format, lint, typecheck, test).
- Output is byte-reproducible: rendering twice yields identical bytes (seeded RNG, no `timestamp`).
