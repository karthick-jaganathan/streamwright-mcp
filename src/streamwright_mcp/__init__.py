"""Deprecated alias of `streamwright.mcp`, kept for one release."""

import warnings

from streamwright.mcp import __version__

warnings.warn(
    "streamwright_mcp is deprecated and will be removed in the next release; import streamwright.mcp instead",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["__version__"]
