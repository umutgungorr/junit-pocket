"""Convert local JUnit reports to a bounded, metadata-only JSON summary."""

import argparse
import json
import os
import re
import stat
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_INPUT_BYTES = 1024 * 1024
NOTICE = "Best effort masking; identifiers may still contain sensitive data."


class ReportError(ValueError):
    """Fixed, payload-free user-facing failure."""


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "Invalid arguments; --junit is required and limits must be in range.\n")


def build_parser():
    parser = SafeArgumentParser(description="Summarize local JUnit XML as JSON.")
    parser.add_argument("--junit", required=True, help="UTF-8 JUnit input (at most 1 MiB)")
    parser.add_argument("-o", "--output", help="Create a new output file; default: stdout")
    parser.add_argument("--max-items", type=int, default=20, help="Failure list limit: 1..100")
    return parser


def mask_text(text):
    text = re.sub(r"(?i)API_KEY=\S+", "API_KEY=[REDACTED]", text)
    text = re.sub(r"(?i)Bearer\s+\S+", "Bearer [REDACTED]", text)
    text = re.sub(r"ghp_[A-Za-z0-9_]+", "[REDACTED]", text)
    return text[:160]


def _local_name(tag):
    return tag.rsplit("}", 1)[-1]


def _read_input(path):
    try:
        metadata = path.lstat()
    except OSError:
        raise ReportError("Cannot read input file.") from None
    if stat.S_ISLNK(metadata.st_mode):
        raise ReportError("Input symbolic link is not supported.")
    if not stat.S_ISREG(metadata.st_mode):
        raise ReportError("Input must be a regular file.")
    if metadata.st_size > MAX_INPUT_BYTES:
        raise ReportError("Input exceeds the size limit.")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    flags |= getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode):
                raise ReportError("Input must be a regular file.")
            if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
                raise ReportError("Input file changed while opening.")
            raw = stream.read(MAX_INPUT_BYTES + 1)
    except OSError:
        raise ReportError("Cannot read input file.") from None
    if len(raw) > MAX_INPUT_BYTES:
        raise ReportError("Input exceeds the size limit.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError:
        raise ReportError("Input must use UTF-8 encoding.") from None
    if "\x00" in text:
        raise ReportError("Input must use UTF-8 XML text without null bytes.")
    if re.search(r"<!\s*(DOCTYPE|ENTITY)\b", text, flags=re.IGNORECASE):
        raise ReportError("XML entity declarations are not supported.")
    return text


def _build_report(text, max_items):
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        raise ReportError("Invalid JUnit XML.") from None
    if _local_name(root.tag) not in {"testsuite", "testsuites"}:
        raise ReportError("Invalid JUnit root element.")
    cases = [node for node in root.iter() if _local_name(node.tag) == "testcase"]
    if not cases:
        for suite in root.iter():
            if _local_name(suite.tag) not in {"testsuite", "testsuites"}:
                continue
            try:
                declared = int(suite.get("tests", "0"))
            except ValueError:
                raise ReportError("Invalid JUnit declared test count.") from None
            if declared > 0:
                raise ReportError("Declared tests have no testcase records.")
    summary = {"tests": len(cases), "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    failures = []
    total_failures = 0
    for case in cases:
        child_tags = {_local_name(child.tag) for child in case}
        if "error" in child_tags:
            kind, count = "error", "errors"
        elif "failure" in child_tags:
            kind, count = "failure", "failed"
        elif "skipped" in child_tags:
            kind, count = None, "skipped"
        else:
            kind, count = None, "passed"
        summary[count] += 1
        if kind is not None:
            total_failures += 1
            if len(failures) < max_items:
                failures.append(
                    {
                        "kind": kind,
                        "name": mask_text(case.get("name", "")),
                        "classname": mask_text(case.get("classname", "")),
                    }
                )
    return {
        "schema_version": "1.0",
        "summary": summary,
        "failures": failures,
        "omitted_failures": total_failures - len(failures),
        "notice": NOTICE,
    }


def _write_report(content, output):
    if output is None:
        try:
            sys.stdout.write(content)
        except OSError:
            raise ReportError("Cannot write output.") from None
        return
    try:
        with Path(output).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    except FileExistsError:
        raise ReportError("Output overwrite is not allowed.") from None
    except OSError:
        raise ReportError("Cannot create output file.") from None


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    try:
        if not 1 <= args.max_items <= 100:
            raise ReportError("max-items must be in range 1..100.")
        report = _build_report(_read_input(Path(args.junit)), args.max_items)
        _write_report(json.dumps(report, ensure_ascii=False) + "\n", args.output)
    except ReportError as exc:
        sys.stderr.write(f"{exc!s}\n")
        return 2
    return 0
