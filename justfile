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
