#!/usr/bin/env python
# /*************************************************************************
# * Copyright 2026 Karthick Jaganathan
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# * https://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# * See the License for the specific language governing permissions and
# * limitations under the License.
# **************************************************************************/

"""`search_docs`: a keyword search over the shipped guides (engines, installed connectors) and the CLI help."""

import functools
import re
from collections import Counter
from typing import Any, NamedTuple

from streamwright.core.runtime import components

from streamwright.mcp import cli_reference, connectors
from streamwright.mcp.engines import EngineError, EngineRegistry, split_sections

_WORD = re.compile(r"[a-z0-9]+")
_IDENTIFIER = re.compile(r"[a-z0-9]+(?:[._][a-z0-9]+)+")   # snake_case and dotted names, kept whole too
TOP = 10
SNIPPET = 200
TITLE_WEIGHT = 5
NO_HITS = ("No section mentions these words: try fewer or other words, or browse the sections listed by "
           "get_engine_guide, get_connector_guide and get_cli_reference.")


class _Unit(NamedTuple):
    source: str
    section: str
    text: str
    terms: Counter
    title_terms: Counter
    open: dict[str, Any]


def tokens(text: str) -> list[str]:
    """Lowercase words split on anything not a letter or digit, plus the identifiers with `_` or `.` whole (and the
    snake_case parts of a dotted one)."""
    lower = text.lower()
    identifiers = _IDENTIFIER.findall(lower)
    parts = [part for name in identifiers if "." in name for part in name.split(".") if "_" in part]
    return _WORD.findall(lower) + identifiers + parts     # `Service.mutate_x` also counts as `mutate_x`


@functools.lru_cache(maxsize=1)
def _index(registry: EngineRegistry) -> tuple[_Unit, ...]:
    """One unit per heading section of every engine and installed connector guide, and per CLI command."""
    units = []

    def add(source: str, section: str, text: str, tool: str, args: dict[str, Any]) -> None:
        units.append(_Unit(source, section, text, Counter(tokens(text)), Counter(tokens(section)),
                           {"tool": tool, "args": args}))

    for engine in registry:
        for title in engine.guide(None)["sections"]:
            add(f"engine:{engine.kind}", title, engine.guide(title)["text"], "get_engine_guide",
                {"kind": engine.kind, "section": title})
    for name in sorted(components.available()):
        for title, text in split_sections(connectors.guide_text(name) or "").items():
            add(f"connector:{name}", title, text, "get_connector_guide", {"name": name, "section": title})
    for command, text in cli_reference.help_texts().items():
        add("cli", command, text, "get_cli_reference", {"command": command})
    return tuple(units)


def _first(lower: str, terms: list[str]) -> int | None:
    """Where the first of `terms` is in `lower` as a whole word (`ad` is not found in `loads`), or None."""
    found = [match.start() for term in terms
             for match in [re.search(r"(?<![a-z0-9])%s(?![a-z0-9])" % re.escape(term), lower)] if match]
    return min(found) if found else None


def _snippet(text: str, terms: list[str]) -> str:
    """The text around the query's first identifier as written (`ad_group`), else around its first word."""
    lower = text.lower()
    position = _first(lower, [term for term in terms if _IDENTIFIER.fullmatch(term)])
    if position is None:
        position = _first(lower, terms)
    start = max(0, position - SNIPPET // 4) if position is not None else 0
    return " ".join(text[start:start + SNIPPET].split())


def search_docs(registry: EngineRegistry, query: str) -> dict[str, Any]:
    """The TOP sections that mention the query's terms most: first those with its identifiers as written
    (`mutate_campaigns`) or its words in order ("update mask"), then more distinct terms, then hits (a hit in the
    title counts TITLE_WEIGHT times)."""
    terms = list(dict.fromkeys(tokens(query or "")))
    if not terms:
        raise EngineError("search_docs needs a query: words or identifiers to look for.")
    whole = [term for term in terms if _IDENTIFIER.fullmatch(term)]    # identifiers as written: they rank first
    phrase = " ".join((query or "").lower().split())
    scored = []
    for unit in _index(registry):
        hits = [unit.terms[term] + TITLE_WEIGHT * unit.title_terms[term] for term in terms]
        if any(hits):
            exact = sum(1 for term in whole if unit.terms[term] or unit.title_terms[term])
            in_order = len(phrase.split()) > 1 and phrase in " ".join(unit.text.lower().split())
            scored.append(((exact, in_order, sum(1 for hit in hits if hit), sum(hits)), unit))
    if any(key[0] for key, _ in scored):          # sections with the identifiers as written: only those
        scored = [(key, unit) for key, unit in scored if key[0]]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    results = [{"source": unit.source, "section": unit.section, "snippet": _snippet(unit.text, terms),
                "open": unit.open} for _, unit in scored[:TOP]]
    return {"query": query, "results": results, **({} if results else {"hint": NO_HITS})}
