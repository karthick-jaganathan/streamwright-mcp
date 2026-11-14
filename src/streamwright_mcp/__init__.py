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

"""Deprecated alias of `streamwright.mcp`, kept for one release."""

import warnings

from streamwright.mcp import __version__

warnings.warn(
    "streamwright_mcp is deprecated and will be removed in the next release; import streamwright.mcp instead",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["__version__"]
