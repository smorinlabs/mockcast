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
        {
            **_demo(title="t", idle_time_limit=2.0),
            "scenes": [{"name": "s", "steps": []}],
        }
    )
    cast = render(demo)
    assert cast.header["version"] == 3
    assert cast.header["term"]["cols"] == 100
    assert cast.header["term"]["type"] == "xterm-256color"
    assert cast.header["title"] == "t"
    assert cast.header["idle_time_limit"] == 2.0


def test_typing_emits_prompt_then_chars_then_enter():
    demo = Demo.model_validate(
        {**_demo(), "scenes": [{"name": "s", "steps": [{"type": "hi"}]}]}
    )
    cast = render(demo)
    events = [(e.interval, e.code, e.data) for e in cast.events]
    assert events == [
        (0.0, "o", "$ "),  # prompt, first event interval is 0.0
        (0.1, "o", "h"),  # 1/cps = 0.1
        (0.1, "o", "i"),
        (0.1, "o", "\r\n"),  # Enter
    ]


def test_output_instant_one_event_with_crlf():
    demo = Demo.model_validate(
        {**_demo(), "scenes": [{"name": "s", "steps": [{"output": "a\nb"}]}]}
    )
    cast = render(demo)
    events = [(e.interval, e.code, e.data) for e in cast.events]
    assert events == [(0.0, "o", "a\r\nb")]


def test_output_lines_streams_each_line():
    demo = Demo.model_validate(
        {
            **_demo(),
            "scenes": [{"name": "s", "steps": [{"output": "a\nb", "stream": "lines"}]}],
        }
    )
    cast = render(demo)
    events = [(e.interval, e.code, e.data) for e in cast.events]
    assert events == [
        (0.0, "o", "a\r\n"),
        (0.08, "o", "b\r\n"),
    ]


def test_output_chars_streams_per_char():
    demo = Demo.model_validate(
        {
            **_demo(),
            "scenes": [{"name": "s", "steps": [{"output": "hi", "stream": "chars"}]}],
        }
    )
    cast = render(demo)
    events = [(e.interval, e.code, e.data) for e in cast.events]
    assert events == [
        (0.0, "o", "h"),  # first event interval is 0.0
        (0.1, "o", "i"),  # 1/cps = 0.1
    ]


def test_pause_and_delay_add_to_next_interval():
    demo = Demo.model_validate(
        {
            **_demo(),
            "scenes": [
                {"name": "s", "steps": [{"pause": 1.0}, {"output": "x", "delay": 0.5}]}
            ],
        }
    )
    cast = render(demo)
    # single event; pause(1.0)+delay(0.5) but first event interval is 0.0
    assert [(e.interval, e.code, e.data) for e in cast.events] == [(0.0, "o", "x")]


def test_banner_and_clear():
    demo = Demo.model_validate(
        {
            **_demo(),
            "scenes": [
                {"name": "s", "steps": [{"clear": True}, {"banner": "--- cut ---"}]}
            ],
        }
    )
    cast = render(demo)
    events = [(e.code, e.data) for e in cast.events]
    assert events == [("o", "\x1b[2J\x1b[H"), ("o", "--- cut ---\r\n")]


def test_explicit_marker_emits_m_event():
    demo = Demo.model_validate(
        {**_demo(), "scenes": [{"name": "s", "steps": [{"marker": "chapter one"}]}]}
    )
    cast = render(demo)
    assert [(e.code, e.data) for e in cast.events] == [("m", "chapter one")]


def test_auto_markers_emit_scene_name_at_start():
    base = _demo()
    base["meta"]["auto_markers"] = True
    demo = Demo.model_validate(
        {**base, "scenes": [{"name": "onboard", "steps": [{"output": "hi"}]}]}
    )
    cast = render(demo)
    assert [(e.code, e.data) for e in cast.events] == [
        ("m", "onboard"),
        ("o", "hi"),
    ]


def test_scene_vars_swap_prompt_identity():
    base = _demo(prompt="{user}@{host} $ ")
    demo = Demo.model_validate(
        {
            **base,
            "vars": {"user": "maya", "host": "laptop"},
            "scenes": [
                {"name": "a", "steps": [{"type": "x"}]},
                {
                    "name": "b",
                    "vars": {"user": "sam", "host": "ws"},
                    "steps": [{"type": "y"}],
                },
            ],
        }
    )
    cast = render(demo)
    prompts = [e.data for e in cast.events if e.code == "o" and "@" in e.data]
    assert prompts == ["maya@laptop $ ", "sam@ws $ "]


def test_render_is_deterministic_with_jitter():
    spec = {
        "meta": {"typing": {"cps": 12, "jitter": 0.5}, "seed": 7, "prompt": "$ "},
        "scenes": [{"name": "s", "steps": [{"type": "acme ai status"}]}],
    }
    a = render(Demo.model_validate(spec))
    b = render(Demo.model_validate(spec))
    assert [(e.interval, e.code, e.data) for e in a.events] == [
        (e.interval, e.code, e.data) for e in b.events
    ]
