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

import asyncio
import json
import re
from collections import Counter

import pytest
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from streamwright.mcp import search
from streamwright.mcp.engines import discover_engines
from streamwright.mcp.server import MAX_RESULT_CHARS, ToolResult, _add_tool, cap_result


@pytest.fixture(scope="module")
def units():
    return search._index(discover_engines())


def _rarest(candidates, units):
    """The candidate term that the fewest sections hold (ties: alphabetical), so the search must find it."""
    frequency = Counter(term for unit in units for term in set(unit.terms) | set(unit.title_terms))
    return min(sorted(candidates), key=lambda term: frequency[term] or len(units) + 1)


def test_a_word_of_a_guide_heading_finds_that_section(call, units):
    word = _rarest({term for unit in units for term in search.tokens(unit.section) if re.fullmatch(r"[a-z]{4,}", term)},
                   units)

    results = call("search_docs", query=word.upper())["results"]

    assert results and word in search.tokens(results[0]["section"])


def test_an_identifier_with_underscores_is_found_whole_and_the_hit_opens(call, units):
    identifier = _rarest({term for unit in units for term in unit.terms if re.fullmatch(r"[a-z]+(_[a-z]+)+", term)},
                         units)

    results = call("search_docs", query=identifier)["results"]

    assert results and identifier in results[0]["snippet"].lower()
    opened = call(results[0]["open"]["tool"], **results[0]["open"]["args"])
    assert identifier in json.dumps(opened).lower()
    assert {result["source"].split(":")[0] for result in results} <= {"engine", "connector", "cli"}


def test_a_blank_query_is_an_error_and_no_hits_give_a_hint(call):
    with pytest.raises(ToolError, match="needs a query"):
        call("search_docs", query="  ")
    assert call("search_docs", query="qqzzxj")["results"] == []
    assert "hint" in call("search_docs", query="qqzzxj")


def test_every_tool_result_is_capped():
    server = MCPServer("capped")

    def oversized() -> ToolResult:
        return {"text": "x" * 50_000, "rows": list(range(20_000)), "nested": {"items": [{"y": "y" * 5_000}] * 50}}

    _add_tool(server, oversized)
    result = asyncio.run(server.call_tool("oversized", {})).structured_content
    result = result.get("result", result)

    assert len(json.dumps(result)) <= MAX_RESULT_CHARS
    assert {"text", "rows", "nested"} <= set(result) and result["truncated"] is True and "search_docs" in result["hint"]
    assert cap_result({"small": [1, 2]}) == {"small": [1, 2]}
