"""Tests that generated code cannot replace or weaken."""

from junit_pocket.main import build_parser, main


def test_parser_has_help() -> None:
    help_text = build_parser().format_help()

    assert "usage:" in help_text.lower()


def test_help_exits_successfully() -> None:
    assert main(["--help"]) == 0
