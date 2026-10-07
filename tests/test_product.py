"""Independent behavioral contract frozen before live generation; synthetic inputs only."""

import json
import socket

import pytest

from junit_pocket.main import main


def source(tmp_path, text, name="input.xml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def invoke(path, capsys, *args):
    before = path.read_bytes()
    assert main(["--junit", str(path), *args]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.endswith("\n")
    assert path.read_bytes() == before
    return json.loads(captured.out)


def valid_control(tmp_path, capsys):
    path = source(tmp_path, '<testsuite><testcase name="ok"/></testsuite>', "control.xml")
    data = invoke(path, capsys)
    assert data["summary"] == {"tests": 1, "passed": 1, "failed": 0, "errors": 0, "skipped": 0}


def test_counts_and_private_content_exclusion(tmp_path, capsys):
    path = source(
        tmp_path,
        '<testsuites><testsuite tests="999"><testcase name="pass"/>'
        '<testcase name="skip"><skipped/></testcase>'
        '<testcase name="fail" classname="tests.api" file="PRIVATE_PATH" line="5">'
        '<failure message="PRIVATE_MESSAGE">PRIVATE_BODY</failure>'
        "<system-out>PRIVATE_STDOUT</system-out></testcase>"
        '<testcase name="err"><error>PRIVATE_ERROR</error></testcase>'
        "</testsuite></testsuites>",
    )
    data = invoke(path, capsys)
    assert set(data) == {"schema_version", "summary", "failures", "omitted_failures", "notice"}
    assert data["schema_version"] == "1.0"
    assert data["summary"] == {"tests": 4, "passed": 1, "failed": 1, "errors": 1, "skipped": 1}
    assert data["failures"] == [
        {"kind": "failure", "name": "fail", "classname": "tests.api"},
        {"kind": "error", "name": "err", "classname": ""},
    ]
    assert data["omitted_failures"] == 0
    assert "PRIVATE_" not in json.dumps(data)
    assert "best effort" in data["notice"].lower()


def test_namespace_nested_suites_and_precedence(tmp_path, capsys):
    path = source(
        tmp_path,
        '<testsuites xmlns="urn:junit"><testsuite><testsuite>'
        '<testcase name="mixed"><skipped/><failure/><error/></testcase>'
        '<testcase name="failure"><skipped/><failure/></testcase>'
        "<testcase/><testcase><skipped/></testcase>"
        "</testsuite></testsuite></testsuites>",
    )
    data = invoke(path, capsys)
    assert data["summary"] == {"tests": 4, "passed": 1, "failed": 1, "errors": 1, "skipped": 1}
    assert [item["kind"] for item in data["failures"]] == ["error", "failure"]


def test_bom_and_empty_suite(tmp_path, capsys):
    data = invoke(source(tmp_path, '\ufeff<testsuite tests="0"/>'), capsys)
    assert data["summary"] == {"tests": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    assert data["failures"] == []


def test_caps_and_omission_count(tmp_path, capsys):
    cases = "".join(
        f'<testcase name="{i}_{"x" * 500}" classname="{"y" * 500}"><failure/></testcase>'
        for i in range(7)
    )
    data = invoke(source(tmp_path, f"<testsuite>{cases}</testsuite>"), capsys, "--max-items", "2")
    assert data["summary"]["failed"] == 7
    assert len(data["failures"]) == 2 and data["omitted_failures"] == 5
    assert all(
        len(item["name"]) <= 160 and len(item["classname"]) <= 160 for item in data["failures"]
    )


@pytest.mark.parametrize(
    "secret",
    [
        "API_KEY=synthetic-private-value",
        "Bearer synthetic-private-value",
        "ghp_syntheticabcdefghijklmnopqrstuvwxyz",
    ],
)
def test_supported_identifier_masking(tmp_path, capsys, secret):
    data = invoke(
        source(
            tmp_path,
            f'<testsuite><testcase name="{secret}" classname="{secret}">'
            "<failure/></testcase></testsuite>",
        ),
        capsys,
    )
    exported = json.dumps(data)
    assert "synthetic-private-value" not in exported
    assert "ghp_syntheticabcdefghijklmnopqrstuvwxyz" not in exported
    assert "[REDACTED]" in exported


def test_mask_before_clip(tmp_path, capsys):
    text = "x" * 130 + " Bearer " + "s" * 100
    data = invoke(
        source(tmp_path, f'<testsuite><testcase name="{text}"><failure/></testcase></testsuite>'),
        capsys,
    )
    assert "ssss" not in data["failures"][0]["name"]
    assert "[REDACTED]" in data["failures"][0]["name"]


def test_output_file_and_refuse_overwrite(tmp_path, capsys):
    path = source(tmp_path, '<testsuite><testcase name="ok"/></testsuite>')
    output = tmp_path / "report.json"
    assert main(["--junit", str(path), "-o", str(output)]) == 0
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
    before = output.read_bytes()
    assert json.loads(before)["summary"]["passed"] == 1
    assert main(["--junit", str(path), "--output", str(output)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "overwrite" in captured.err.lower()
    assert output.read_bytes() == before


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("<testsuite>PRIVATE_PAYLOAD", "junit"),
        ("<other>PRIVATE_PAYLOAD</other>", "junit"),
        ('<!DOCTYPE testsuite [<!ENTITY x "PRIVATE_PAYLOAD">]><testsuite/>', "entity"),
        ('<testsuite tests="2"/>', "testcase"),
    ],
)
def test_rejected_xml_actual_reason(tmp_path, capsys, text, reason):
    valid_control(tmp_path, capsys)
    path = source(tmp_path, text)
    before = path.read_bytes()
    output = tmp_path / "rejected.json"
    assert main(["--junit", str(path), "-o", str(output)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and reason in captured.err.lower()
    assert "PRIVATE_PAYLOAD" not in captured.err and not output.exists()
    assert path.read_bytes() == before


@pytest.mark.parametrize("limit", ["0", "101", "-1"])
def test_numeric_limits(tmp_path, capsys, limit):
    valid_control(tmp_path, capsys)
    path = source(tmp_path, "<testsuite/>")
    output = tmp_path / "bad-limit.json"
    assert main(["--junit", str(path), "--max-items", limit, "-o", str(output)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "range" in captured.err.lower()
    assert not output.exists()


def test_non_utf8(tmp_path, capsys):
    valid_control(tmp_path, capsys)
    path = tmp_path / "utf16.xml"
    path.write_bytes("<testsuite/>".encode("utf-16"))
    assert main(["--junit", str(path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "utf-8" in captured.err.lower()


def test_size_limit(tmp_path, capsys):
    valid_control(tmp_path, capsys)
    path = source(tmp_path, "<testsuite><!--" + "x" * (1024 * 1024) + "--></testsuite>")
    assert main(["--junit", str(path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "size limit" in captured.err.lower()


def test_symlink_and_missing_input(tmp_path, capsys):
    valid_control(tmp_path, capsys)
    real = source(tmp_path, "<testsuite/>")
    link = tmp_path / "link.xml"
    link.symlink_to(real)
    assert main(["--junit", str(link)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "symbolic link" in captured.err.lower()
    assert main(["--junit", str(tmp_path / "missing.xml")]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "input" in captured.err.lower()


def test_help_missing_args_and_no_network(tmp_path, capsys, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Product attempted network access")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    assert main(["--help"]) == 0
    assert "--junit" in capsys.readouterr().out
    assert main([]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err
    data = invoke(source(tmp_path, "<testsuite><testcase/></testsuite>"), capsys)
    assert data["summary"]["passed"] == 1
