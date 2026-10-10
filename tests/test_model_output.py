import pytest
from graph.llm import parse_json_response


def test_json_text_blocks_are_supported():
    assert parse_json_response([{'type': 'text', 'text': '{"validation_result":"sufficient"}'}]) == {'validation_result': 'sufficient'}


def test_non_object_json_is_rejected():
    with pytest.raises(ValueError):
        parse_json_response('[]')
