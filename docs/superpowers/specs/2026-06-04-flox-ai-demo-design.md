# Design: `mockcast` — vaporware demos as code (asciicast v3)

**Date:** 2026-06-04
**Status:** Approved (pending spec review)

## Summary

A CLI that turns a **declarative YAML demo-script** into a valid **asciicast v3
`.cast` file** — a scripted, fake terminal session for a CLI product that does
not exist yet. You author the imagined interaction (commands "typed," outputs
"printed," timing, chapter markers); the tool emits a reproducible `.cast` you
can play with the real `asciinema` player and share. No PTY, no real product —
**vaporware demos as code.**

The first demo it renders is the hero cut for an imagined product, **`acme ai`**
(a tool that manages AI coding harnesses — Claude Code, Codex, Gemini CLI,
OpenCode — plus their profiles, skills, and scopes).

## Goals

- Author a fake CLI session in readable, diffable YAML.
- Emit a **spec-valid asciicast v3** file that plays in `asciinema` ≥ 3.0.
- **Deterministic / byte-reproducible** output (seeded timing jitter, no
  wall-clock timestamp) so golden-file tests are stable.
- Support a continuous "day-in-the-life" narrative with **chapter markers** for
  navigation.

## Non-Goals (YAGNI)

- Recording real terminal sessions (no PTY).
- Building the real `acme ai` product.
- A color/styling DSL — authors embed raw ANSI escapes in output strings.
- Uploading to asciinema.org, SVG export, web-player embedding. (GIF export was
  added later via a `gif` command that shells out to `agg`.)
- `i` (input) / `r` (resize) / `x` (exit) event codes — only `o` and `m` are used.

## Preconditions

- **`asciinema` ≥ 3.0 required** for playback and verification. v3 is an
  asciinema 3.x (Rust) format; the legacy 2.x (Python) CLI does not handle it.
  Confirmed installed during design: **`asciinema 3.2.0`** at
  `/opt/homebrew/bin/asciinema`.

## Architecture

Three I/O-free units behind a thin CLI:

```
demo.yaml ──▶ [parser/validator] ──▶ [engine] ──▶ [v3 writer] ──▶ out.cast ──▶ asciinema play
 (author)        models.py            engine.py     writer.py                    (real player)
```

- **`models.py`** — pydantic v2 schema + validation. Defines what a valid demo
  file is; produces friendly errors. No I/O.
- **`engine.py`** — pure function: `validated demo → list[Event]`. All timing,
  typing, prompt, and marker logic. No filesystem access (enables golden tests).
- **`writer.py`** — serializes header + events to a `.cast` (newline-delimited
  JSON; intervals rounded to 3 decimals).
- **`cli.py`** — `render`, `play`, `validate`.

Each unit is understandable and testable in isolation. The engine is the only
unit with interesting logic and is deliberately pure.

## The YAML demo-script schema

```yaml
meta:
  title: "acme ai — a day in the life"
  term: { cols: 100, rows: 30, type: xterm-256color }
  typing: { cps: 18, jitter: 0.35 }      # chars/sec + randomness
  prompt: "{user}@{host} {cwd} $ "
  pauses: { after_command: 0.4, between_scenes: 1.0 }
  idle_time_limit: 2.0
  seed: 42                               # makes jitter reproducible
  auto_markers: true                     # drop a marker per scene (named after it)

vars: { user: maya, host: laptop, cwd: "~/acme" }

scenes:
  - name: onboard
    steps:
      - type: "acme ai profile install acme-team"
      - output: |
          Resolving acme-team…
          ✔ claude-code  installed
          ✔ codex        already up to date
          ✔ gemini-cli   installed
          ✔ synced 7 skills · logged in as maya
        stream: lines                    # reveal line-by-line
      - pause: 1.0

  - name: teammate                       # the two-machine trick
    vars: { user: sam, host: workstation }
    steps:
      - banner: "─── Sam's machine ───"
      - marker: "Sam's machine"
      - type: "acme ai search recipe"
```

### Step vocabulary (deliberately small)

| Step | Behavior |
|------|----------|
| `type: "<cmd>"` | render the active prompt, then "type" the command char-by-char (cps + seeded jitter), then Enter (`\r\n`) + `after_command` pause |
| `output: "<text>"` | print text; modifier `stream: instant\|lines\|chars` (default `instant`), optional `delay:` seconds before |
| `pause: <sec>` | idle gap (think time) — adds to the next event's interval |
| `banner: "<text>"` | print a styled scene-divider line (set dressing) |
| `clear: true` | clear the screen (`[2J[H`) |
| `marker: "<label>"` | emit a v3 `m` event → navigable chapter marker |

- Scene-level `vars:` / `prompt:` override globals — this is how identity swaps
  ("Sam's machine") work. It is the only state the engine tracks across steps.
- Authors may embed raw ANSI escapes in `output`/`banner` strings for color.

## Engine semantics

- Carries a running **"interval since last event"** (seconds). `pause` and
  `output.delay` add to it; the accumulated interval attaches to the *next*
  emitted event.
- **First event interval** is `0.0` (the cast starts immediately).
- **Typing:** each character → one `o` event, interval `1/cps` perturbed by
  `jitter` drawn from a **seeded RNG**. Enter → `\r\n`, then `after_command`
  pause.
- **Prompt:** templated from the active `vars` (`{user}`, `{host}`, `{cwd}`),
  rendered before each `type` step. Scene-level `vars` shadow globals.
- **Output streaming:** `instant` → one `o` event for the whole block;
  `lines` → one `o` event per line, separated by a small interval;
  `chars` → one `o` event per character at the typing cadence (typewriter reveal).
- **Scene boundaries:** `between_scenes` pause is added to the interval before
  the first event of each scene after the first.
- **Markers:** an explicit `marker:` step emits `[interval, "m", label]`. When
  `meta.auto_markers` is true, the engine also emits a marker named after each
  scene at the scene's start (explicit markers add to these).
- **Determinism:** seeded RNG + omitted `timestamp` ⇒ identical bytes across runs.

## asciicast v3 mapping (verified against the spec)

- **Header** (line 1, JSON object): `version: 3` (required), `term: {cols, rows,
  type}` (cols/rows required), `title`, `idle_time_limit` (optional).
  `timestamp` **omitted** for reproducibility.
- **Events**: `[interval, code, data]` where `interval` is **relative** seconds
  since the previous event, rounded to 3 decimals. Codes used: `o` (output),
  `m` (marker). Data is a valid UTF-8 JSON string.

## CLI surface

- `mockcast render <demo.yaml> -o <out.cast>` — validate, then render.
- `mockcast play <demo.yaml>` — render to a temp `.cast`, then shell out to
  `asciinema play`.
- `mockcast validate <demo.yaml>` — schema-check only, friendly errors.
- `mockcast gif <demo.yaml> -o <out.gif> [--speed S] [--theme T]` — render to a
  temp `.cast`, then shell out to `agg` to produce an animated GIF. (Added after
  the original scope; requires `agg`.)

## Tech stack & layout

Python 3.12 · **uv** package · **pydantic v2** · **PyYAML** · **pytest** ·
**ruff** · **ty** · **just**. Console script entry point: `mockcast`.

```
src/mockcast/{__init__,models,engine,writer,cli}.py
tests/{test_models,test_engine,test_writer,test_cli}.py
examples/acme-ai-day.yaml      # the full 10-beat hero cut
docs/superpowers/specs/2026-06-04-flox-ai-demo-design.md
```

## The hero cut (the example demo — 10 beats / chapters)

Single continuous cast; protagonist **Maya** (acme-team) then teammate **Sam**:

1. **Onboard** — `acme ai profile install acme-team` (installs Claude Code,
   "Codex already up to date," Gemini CLI; syncs skills; logs in)
2. **Verify** — `acme ai doctor` (Claude Code auto-updated, one drift auto-fixed)
3. **Launch** — `acme ai launch` (OS-aware start of Claude Code, back to shell)
4. **Usage** — `acme ai usage` (per-tool session/token table)
5. **Search** — `acme ai search recipe` (nothing fits → motivation to build)
6. **Author** — `acme ai skill dev recipe-helper` (dev mode, edit, `skill
   restart`, test live)
7. **Ship** — `acme ai skill sync` → `acme ai skill publish recipe-helper`
8. **Promote** — `acme ai skill use recipe-helper`, flip dev → production
9. **Sam's machine** — banner + identity swap; `acme ai search recipe` now finds
   it → `acme ai profile pull` → Sam gets `recipe-helper` (loop proven)
10. **Status** — `acme ai status` clean summary (the shareable closing frame)

## Testing (TDD-first)

- **Determinism:** with `jitter: 0` the per-char intervals are exactly `1/cps`,
  so a tiny demo's events are asserted exactly (hand-computable). Separately,
  rendering the same seeded demo twice yields byte-identical events. (Proves
  deterministic output without committing a brittle golden `.cast` artifact.)
- **v3 compliance:** header `version == 3`; every event is `[float, code, str]`
  with `code in {"o","m"}` and non-negative intervals; first interval `== 0.0`.
- **Validation:** unknown step types / malformed YAML rejected with clear errors.
- **Prompt/identity:** scene-level `vars` swap changes the rendered prompt.
- **Marker:** `marker` step and `auto_markers` produce `m` events at expected
  positions.

## Acceptance criteria

- `mockcast render examples/acme-ai-day.yaml -o out.cast` produces a
  spec-valid v3 file.
- **Real playback (closes the loop):** `asciinema play out.cast` plays the hero
  cut end-to-end, and the chapter markers appear as navigable points — schema
  validity alone is insufficient. (Automated/non-interactive proxy:
  `asciinema convert -f txt out.cast -` replays the timed stream to text and
  proves asciinema accepts the file. Note: in asciinema 3.x, `cat` is a
  concatenation command, not a dump — use `convert` for the dump.)
- `just all` (format, lint, typecheck, test) passes.

## Open questions / future (not in this prototype)

- asciinema.org upload, SVG export, web-player embed page. (GIF export and
  `stream: chars` were added after the original scope.)
- A Python builder API as a thin wrapper over the YAML model.
- Multi-cast composition (stitching several demo files into one).
