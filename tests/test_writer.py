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
