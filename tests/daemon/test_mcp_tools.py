from types import SimpleNamespace

import pytest

from mail_daemon.mcp_tools import READ_TOOL_NAMES, ToolCallError, parse_tool_result


def _text_block(text: str):
    return SimpleNamespace(text=text)


def test_parse_tool_result_unwraps_list_structured_content():
    result = SimpleNamespace(is_error=False, structured_content={"result": [1, 2, 3]}, content=[])
    assert parse_tool_result(result) == [1, 2, 3]


def test_parse_tool_result_uses_structured_content_directly_when_not_wrapped():
    result = SimpleNamespace(is_error=False, structured_content={"status": "ok"}, content=[])
    assert parse_tool_result(result) == {"status": "ok"}


def test_parse_tool_result_falls_back_to_single_text_block_json():
    result = SimpleNamespace(is_error=False, structured_content=None, content=[_text_block('{"a": 1}')])
    assert parse_tool_result(result) == {"a": 1}


def test_parse_tool_result_falls_back_to_multiple_text_blocks_as_list():
    result = SimpleNamespace(
        is_error=False,
        structured_content=None,
        content=[_text_block('{"a": 1}'), _text_block('{"a": 2}')],
    )
    assert parse_tool_result(result) == [{"a": 1}, {"a": 2}]


def test_parse_tool_result_raises_on_error():
    result = SimpleNamespace(is_error=True, structured_content=None, content=[_text_block("boom")])
    with pytest.raises(ToolCallError):
        parse_tool_result(result)


def test_read_tool_names_never_include_write_tools():
    assert READ_TOOL_NAMES == {"list_recent", "get_email", "search_emails"}
    for write_tool in ("move_to_folder", "move_to_trash", "restore", "unsubscribe"):
        assert write_tool not in READ_TOOL_NAMES
