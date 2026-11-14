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

"""
Workspace confinement for tools that read files named by an MCP client.

A client controls every path and content argument, so paths must stay inside the allowed
workspace roots.
"""

import os
import re

ROOTS_ENV = "STREAMWRIGHT_MCP_ROOTS"
MAX_CONTENT_BYTES = 5 * 1024 * 1024  # the core job loader's limit

_URI_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:/")


class WorkspaceError(ValueError):
    """A path or content argument is outside what the server may read."""


def allowed_roots() -> list[str]:
    """Real paths of the allowed roots: STREAMWRIGHT_MCP_ROOTS (os.pathsep-separated), else the working directory."""
    configured = [entry for entry in os.environ.get(ROOTS_ENV, "").split(os.pathsep) if entry]
    return [os.path.realpath(entry) for entry in configured or [os.getcwd()]]


def resolve_workspace_path(path: str, parameter: str = "path") -> str:
    """
    Returns the real path of `path`, which must be inside an allowed root.

    Raises:
        WorkspaceError: for URIs (s3://, file://, http://, ...), NUL bytes, and paths that
            leave the roots (through `..` or a symlink). The path is not opened.
    """
    if not isinstance(path, str) or not path.strip():
        raise WorkspaceError(f"'{parameter}' must be a non-empty filesystem path.")
    if "\0" in path:
        raise WorkspaceError(f"'{parameter}' is not a valid filesystem path.")
    if _URI_SCHEME.match(path):
        raise WorkspaceError(f"'{parameter}' must be a local filesystem path, not a URI.")
    resolved = os.path.realpath(os.path.expanduser(path))
    for root in allowed_roots():
        if resolved == root or resolved.startswith(root + os.sep):
            return resolved
    raise WorkspaceError(f"'{parameter}' is outside the allowed workspace roots: {', '.join(allowed_roots())} (add "
                         f"more with {ROOTS_ENV}, {os.pathsep}-separated). Tools that take `content` check a "
                         "manifest's text instead of a path.")


def check_content_size(content: str, parameter: str = "content") -> None:
    """Raises WorkspaceError when inline `content` is larger than MAX_CONTENT_BYTES."""
    if len(content.encode("utf-8")) > MAX_CONTENT_BYTES:
        raise WorkspaceError(f"'{parameter}' is larger than {MAX_CONTENT_BYTES} bytes.")

