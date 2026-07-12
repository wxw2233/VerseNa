import pytest
from pathlib import Path
from multimodal.file_parser import FileParser


def test_parse_supported_txt(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("Hello, world!", encoding="utf-8")
    result = FileParser.parse(str(f))
    assert result == "Hello, world!"


def test_parse_supported_py(tmp_path):
    f = tmp_path / "test.py"
    f.write_text("print('hello')", encoding="utf-8")
    result = FileParser.parse(str(f))
    assert "print" in result


def test_parse_unsupported(tmp_path):
    f = tmp_path / "test.exe"
    f.write_bytes(b"\x00\x01")
    result = FileParser.parse(str(f))
    assert "不支持的文件类型" in result


def test_parse_truncation(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("x" * 20000, encoding="utf-8")
    result = FileParser.parse(str(f))
    assert len(result) == 10000
