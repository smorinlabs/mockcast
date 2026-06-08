import json

from mockcast.cli import _agg_command, main


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


def test_render_missing_file_returns_1(tmp_path):
    out = tmp_path / "out.cast"
    rc = main(["render", str(tmp_path / "nope.yaml"), "-o", str(out)])
    assert rc == 1


def test_agg_command_default():
    assert _agg_command("in.cast", "out.gif", None, None) == [
        "agg",
        "in.cast",
        "out.gif",
    ]


def test_agg_command_with_speed_and_theme():
    assert _agg_command("in.cast", "out.gif", 2.0, "dracula") == [
        "agg",
        "--theme",
        "dracula",
        "--speed",
        "2.0",
        "in.cast",
        "out.gif",
    ]
