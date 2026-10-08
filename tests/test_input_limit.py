"""Real larger reports require explicit opt-in; invalid limits never touch output."""

import json

import pytest

from junit_pocket.main import main


def test_large_report_requires_explicit_opt_in(tmp_path, capsys):
    source = tmp_path / "large.xml"
    source.write_text(
        '<testsuite><testcase name="real"/><system-out>'
        + "x" * (1024 * 1024)
        + "</system-out></testsuite>",
        encoding="utf-8",
    )
    assert main(["--junit", str(source)]) == 2
    assert capsys.readouterr().out == ""
    assert main(["--junit", str(source), "--max-input-mib", "2"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["summary"]["passed"] == 1
    assert "system-out" not in json.dumps(report)


@pytest.mark.parametrize("limit", ["0", "17", "-1", "1.5", "invalid"])
def test_invalid_input_limit_creates_no_output(tmp_path, capsys, limit):
    source = tmp_path / "input.xml"
    source.write_text("<testsuite/>", encoding="utf-8")
    output = tmp_path / "result.json"
    assert main(["--junit", str(source), "--max-input-mib", limit, "-o", str(output)]) == 2
    assert not output.exists()
    assert capsys.readouterr().out == ""


def test_opt_in_still_enforces_bound(tmp_path, capsys):
    source = tmp_path / "too-large.xml"
    source.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
    assert main(["--junit", str(source), "--max-input-mib", "2"]) == 2
    assert capsys.readouterr().out == ""
