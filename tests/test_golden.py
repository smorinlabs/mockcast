from pathlib import Path

from mockcast.cli import _load
from mockcast.engine import render
from mockcast.writer import write

FIXTURES = Path(__file__).parent / "fixtures"


def test_golden_cast_is_byte_stable():
    demo = _load(str(FIXTURES / "golden.yaml"))
    expected = (FIXTURES / "golden.cast").read_text()
    assert write(render(demo)) == expected
