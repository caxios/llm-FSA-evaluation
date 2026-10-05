"""P5: JSON extraction, validation and retries."""

import pytest

from src.agents.llm_client import FakeClient
from src.parse.schema import ValuationOutput
from src.parse.validate import NoJSON, extract_json, run_with_retries, validate_output
from tests.p5_helpers import MODEL, valuation_json


@pytest.mark.parametrize("text,expected", [
    ('{"a": 1}', {"a": 1}),
    ('```json\n{"a": 1}\n```', {"a": 1}),
    ('결과입니다:\n{"a": {"b": [1, 2]}, "c": "x}y"}\n이상입니다.', {"a": {"b": [1, 2]},
                                                                 "c": "x}y"}),
    ('{"a": "escaped \\" quote {"}', {"a": 'escaped " quote {'}),
    ('{"a": 1} {"b": 2}', {"a": 1}),
])
def test_extract_json(text, expected):
    assert extract_json(text) == expected


@pytest.mark.parametrize("text", ["no json here", '{"a": 1', '{"a": tru}', "[1, 2]"])
def test_extract_json_failures(text):
    with pytest.raises(NoJSON):
        extract_json(text)


def test_validate_output():
    out, err = validate_output(f"```json\n{valuation_json()}\n```", ValuationOutput)
    assert out is not None and err is None
    out, err = validate_output('{"result": {}}', ValuationOutput)
    assert out is None and "extracted" in err


def test_retry_then_success():
    client = FakeClient(["죄송하지만 도와드릴 수 없습니다.", '{"bad": 1}', valuation_json()])
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    out, raws, err = run_with_retries(client, msgs, MODEL, ValuationOutput)
    assert out is not None and err is None and len(raws) == 3
    assert raws[0].refusal
    retry_turn = client.calls[2]
    assert retry_turn[:2] == msgs and retry_turn[-1]["role"] == "user"
    assert "스키마에 맞지 않습니다" in retry_turn[-1]["content"]
    assert retry_turn[-2] == {"role": "assistant", "content": '{"bad": 1}'}


def test_final_failure():
    client = FakeClient(["nope", "nope", "nope", "unused"])
    out, raws, err = run_with_retries(client, [{"role": "user", "content": "u"}], MODEL,
                                      ValuationOutput)
    assert out is None and len(raws) == 3 and err
    assert client.responses == ["unused"]
