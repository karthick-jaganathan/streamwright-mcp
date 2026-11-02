"""`get_cli_reference`: the live help of the `streamwright` commands, read from the CLI's own parsers."""

import argparse
import sys
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError
from streamwright.core.cli import command_parsers

SHARED_JOB_OPTIONS = "job"  # command_parsers() publishes the options every job command takes under this key


def _children(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def _usage_line(parser: argparse.ArgumentParser) -> str:
    return parser.format_usage().strip()


def _describe(words: list[str], parser: argparse.ArgumentParser) -> dict[str, Any]:
    children = _children(parser)
    return {
        "command": " ".join(words),
        "usage": _usage_line(parser),
        "help_text": parser.format_help(),
        "subcommands": {name: _usage_line(child) for name, child in children.items()} or None,
        "run": f"streamwright {' '.join(words)} --help",
        "fallback": f"{sys.executable} -m streamwright.core.cli {' '.join(words)} --help",
    }


def get_cli_reference(command: str | None = None) -> dict[str, Any]:
    """The commands (no `command`), or the usage and help of one command such as `validate` or `duckdb run`."""
    parsers = command_parsers()
    job_options = parsers.pop(SHARED_JOB_OPTIONS, None)
    words = (command or "").split()
    if not words:
        return {
            "binary": "streamwright",
            "alias": "sw",
            "commands": {name: _usage_line(parser) for name, parser in sorted(parsers.items())},
            "job_options": job_options.format_help() if job_options else None,
            "run": "streamwright --help",
            "fallback": f"{sys.executable} -m streamwright.core.cli --help",
        }
    parser, path = parsers.get(words[0]), words[:1]
    for word in words[1:]:
        parser = _children(parser).get(word) if parser is not None else None
        path.append(word)
    if parser is None:
        raise ToolError(f"Unknown command '{command}'; commands: {', '.join(sorted(parsers))}.")
    return _describe(path, parser)
