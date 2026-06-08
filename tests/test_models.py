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
    # valid combos
    s = Step.model_validate({"output": "x", "stream": "lines"})
    assert s.stream == "lines"
    c = Step.model_validate({"output": "x", "stream": "chars"})
    assert c.stream == "chars"


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        Demo.model_validate({"scenes": [{"name": "s", "steps": [{"typo": "oops"}]}]})


def test_clear_true_is_a_valid_action():
    s = Step.model_validate({"clear": True})
    assert s.clear is True


def test_clear_false_is_rejected():
    with pytest.raises(ValidationError):
        Step.model_validate({"clear": False})
