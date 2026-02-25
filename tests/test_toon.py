"""Unit tests for the TOON serializer."""

from __future__ import annotations

from xl.help.toon import to_toon


def test_scalar_values():
    data = {"name": "xl", "version": "1.0.0", "count": 42}
    result = to_toon(data)
    assert "name: xl" in result
    assert "version: 1.0.0" in result
    assert "count: 42" in result


def test_boolean_values():
    data = {"enabled": True, "disabled": False}
    result = to_toon(data)
    assert "enabled: true" in result
    assert "disabled: false" in result


def test_none_omitted():
    data = {"name": "xl", "missing": None, "count": 1}
    result = to_toon(data)
    assert "name: xl" in result
    assert "missing" not in result
    assert "count: 1" in result


def test_nested_dict():
    data = {"outer": {"inner": "value", "num": 5}}
    result = to_toon(data)
    assert "outer:" in result
    assert "  inner: value" in result
    assert "  num: 5" in result


def test_simple_array():
    data = {"items": ["a", "b", "c"]}
    result = to_toon(data)
    assert "items[3]: a,b,c" in result


def test_uniform_object_array():
    data = {
        "options": [
            {"flag": "--file", "type": "text", "required": "true"},
            {"flag": "--name", "type": "text", "required": "false"},
        ]
    }
    result = to_toon(data)
    assert "options[2]:" in result
    assert "flag,type,required" in result
    assert "--file,text,true" in result
    assert "--name,text,false" in result


def test_empty_dict():
    result = to_toon({})
    assert result == ""


def test_empty_array():
    data = {"items": []}
    result = to_toon(data)
    assert "items[0]:" in result


def test_string_with_comma():
    data = {"desc": "hello, world"}
    result = to_toon(data)
    assert 'desc: "hello, world"' in result


def test_float_value():
    data = {"pi": 3.14}
    result = to_toon(data)
    assert "pi: 3.14" in result


def test_mixed_nesting():
    data = {
        "name": "xl",
        "groups": [
            {"name": "wb", "description": "Workbook operations"},
            {"name": "table", "description": "Table operations"},
        ],
        "config": {"debug": False},
    }
    result = to_toon(data)
    assert "name: xl" in result
    assert "groups[2]:" in result
    assert "name,description" in result
    assert "wb,Workbook operations" in result
    assert "config:" in result
    assert "  debug: false" in result
