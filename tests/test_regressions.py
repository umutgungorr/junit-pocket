"""Regressions for problems observed in the unchanged initial Gemini draft."""

import json
import os
from unittest.mock import patch

from junit_pocket.main import main


def test_utf16_with_actual_testcase_is_rejected(tmp_path, capsys):
    path = tmp_path / "input.xml"
    path.write_bytes("<testsuite><testcase/></testsuite>".encode("utf-16"))
    assert main(["--junit", str(path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "utf-8" in captured.err.lower()


def test_unknown_root_with_actual_testcase_is_rejected(tmp_path, capsys):
    path = tmp_path / "input.xml"
    path.write_text("<other><testcase/></other>", encoding="utf-8")
    assert main(["--junit", str(path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "junit" in captured.err.lower()


def test_output_race_preserves_existing_file(tmp_path, capsys):
    source = tmp_path / "input.xml"
    source.write_text("<testsuite><testcase/></testsuite>", encoding="utf-8")
    output = tmp_path / "report.json"
    output.write_text("existing marker", encoding="utf-8")
    with patch("os.path.exists", return_value=False):
        assert main(["--junit", str(source), "-o", str(output)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "overwrite" in captured.err.lower()
    assert output.read_text(encoding="utf-8") == "existing marker"


def test_unreadable_input_returns_fixed_error(tmp_path, capsys, monkeypatch):
    source = tmp_path / "input.xml"
    source.write_text("<testsuite/>", encoding="utf-8")

    def denied(*args, **kwargs):
        raise PermissionError("PRIVATE_PAYLOAD")

    monkeypatch.setattr(os, "open", denied)
    assert main(["--junit", str(source)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "input" in captured.err.lower()
    assert "PRIVATE_PAYLOAD" not in captured.err


def test_directory_and_dangling_output_symlink_are_not_overwritten(tmp_path, capsys):
    source = tmp_path / "input.xml"
    source.write_text("<testsuite/>", encoding="utf-8")
    assert main(["--junit", str(source), "-o", str(tmp_path)]) == 2
    assert capsys.readouterr().out == ""
    target = tmp_path / "absent.json"
    output = tmp_path / "link.json"
    output.symlink_to(target)
    assert main(["--junit", str(source), "-o", str(output)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "overwrite" in captured.err.lower()
    assert not target.exists()


def test_default_limit_and_unicode_are_deterministic(tmp_path, capsys):
    source = tmp_path / "input.xml"
    cases = "".join(
        f'<testcase name="başarısız_{number}"><failure/></testcase>' for number in range(24)
    )
    source.write_text(f"<testsuite>{cases}</testsuite>", encoding="utf-8")
    assert main(["--junit", str(source)]) == 0
    first = capsys.readouterr().out
    assert main(["--junit", str(source)]) == 0
    assert capsys.readouterr().out == first
    data = json.loads(first)
    assert data["summary"]["failed"] == 24
    assert len(data["failures"]) == 20 and data["omitted_failures"] == 4
    assert data["failures"][0]["name"] == "başarısız_0"
