from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

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
    _load(args.demo)
    print("OK")
    return 0


def cmd_play(args: argparse.Namespace) -> int:
    cast = render(_load(args.demo))
    with tempfile.NamedTemporaryFile("w", suffix=".cast", delete=False) as handle:
        handle.write(write(cast))
        path = handle.name
    try:
        return subprocess.run(["asciinema", "play", path]).returncode
    finally:
        Path(path).unlink(missing_ok=True)


def _agg_command(
    cast_path: str, output: str, speed: float | None, theme: str | None
) -> list[str]:
    cmd = ["agg"]
    if theme is not None:
        cmd += ["--theme", theme]
    if speed is not None:
        cmd += ["--speed", str(speed)]
    cmd += [cast_path, output]
    return cmd


def cmd_gif(args: argparse.Namespace) -> int:
    cast = render(_load(args.demo))
    with tempfile.NamedTemporaryFile("w", suffix=".cast", delete=False) as handle:
        handle.write(write(cast))
        path = handle.name
    try:
        rc = subprocess.run(
            _agg_command(path, args.output, args.speed, args.theme)
        ).returncode
    finally:
        Path(path).unlink(missing_ok=True)
    if rc == 0:
        print(f"wrote {args.output}")
    return rc


def main(argv: list[str] | None = None) -> int:
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

    gif_p = sub.add_parser("gif", help="render then agg to an animated GIF")
    gif_p.add_argument("demo")
    gif_p.add_argument("-o", "--output", required=True)
    gif_p.add_argument("--speed", type=float, default=None)
    gif_p.add_argument("--theme", default=None)
    gif_p.set_defaults(func=cmd_gif)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, ValidationError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
