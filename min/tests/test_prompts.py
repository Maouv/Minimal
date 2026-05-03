# min/tests/test_prompts.py — T1: Prompt Rendering unit tests

import pytest
import jinja2

from prompts.loader import load_prompt
from prompts import init_system, ask_system_prompt, edit_system_prompt


def test_init_prompt_renders():
    result = init_system()
    assert result
    assert "MINIMAL.md" in result


def test_ask_prompt_renders():
    result = ask_system_prompt({"file.py": "print('hello')"})
    assert result
    assert "file.py" in result


def test_ask_prompt_empty_files():
    result = ask_system_prompt({})
    assert result
    assert "(none)" in result


def test_edit_block_renders():
    result = edit_system_prompt("block", {"x.py": "def foo(): pass"})
    assert result
    assert "SEARCH" in result
    assert "REPLACE" in result


def test_edit_udiff_renders():
    result = edit_system_prompt("udiff", {"x.py": "def foo(): pass"})
    assert result
    assert "diff" in result
    assert "---" in result


def test_edit_whole_renders():
    result = edit_system_prompt("whole", {"x.py": "def foo(): pass"})
    assert result
    assert "whole file" in result


def test_missing_prompt_file():
    with pytest.raises(FileNotFoundError):
        load_prompt("nonexistent")


def test_missing_jinja_var():
    with pytest.raises(jinja2.UndefinedError):
        load_prompt("ask")  # file_list tidak di-pass
