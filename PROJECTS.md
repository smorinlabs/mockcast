# Projects

Status: `[?]` idea · `[ ]` scoped · `[~]` in progress · `[x]` done · `[-]` won't do · `[>]` superseded

---

## [x] Project P01: mockcast — scripted terminal demos → asciicast v3 (+ GIF) (v0.1.0)
**Goal**: A CLI that renders declarative YAML demo-scripts into valid asciicast v3
`.cast` files (and animated GIFs via `agg`) — "vaporware demos as code." Output is
byte-reproducible (seeded RNG, no timestamp). Ships example demos for an imagined
`acme ai` product plus an ANSI-styling showcase.

**Out of Scope**
- Recording real terminal sessions (no PTY)
- Building any real product the demos depict
- asciinema.org upload, SVG export, web-player embed page

### Tests & Tasks
- [x] [P01-T01] pydantic schema + validation (`models.py`)
- [x] [P01-T02] pure engine `render(Demo)->Cast` — timing, typing, markers, identity
- [x] [P01-T03] v3 serializer (`writer.py`)
- [x] [P01-T04] CLI `render` / `validate` / `play`
- [x] [P01-T05] hero-cut example + ANSI-styled example
- [x] [P01-T06] `gif` command (shell out to `agg`, `--speed`/`--theme`)
- [x] [P01-T07] rename tool flox-demo → mockcast
- [x] [P01-T08] publish repo to smorinlabs/mockcast (public)
- [x] [P01-T09] de-flox demo content → `acme ai`
- [x] [P01-T10] project hygiene (description, LICENSE, PROJECTS.md)
- [x] [P01-T11] render + embed demo GIFs (media/hero.gif, media/styled.gif)
- [x] [P01-T12] GitHub Actions CI (`just all`) + README badge
- [x] [P01-T13] `stream: chars` mode + committed golden-file test
- [x] [P01-T14] tag + release v0.1.0
- [x] [P01-TS01] schema validation tests
- [x] [P01-TS02] engine timing/marker/identity + determinism tests
- [x] [P01-TS03] v3 serialization tests
- [x] [P01-TS04] CLI render/validate + `_agg_command` builder tests
- [x] [P01-TS05] golden-file `.cast` fixture test

### Automated Verification
- `make check` (uv + asciinema present), `just all` (format, lint, typecheck, test) green
- `mockcast render examples/acme-ai-day.yaml -o out.cast` → spec-valid v3
- `asciinema convert -f txt out.cast -` replays the narrative

### Manual Verification
- `asciinema play out.cast` — timed playback with navigable chapter markers
- `mockcast gif examples/styled-output.yaml -o styled.gif --theme dracula` → valid GIF
