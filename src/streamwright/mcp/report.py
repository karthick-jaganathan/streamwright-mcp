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

"""The one result model of every validate tool: a verdict plus the engine's `Issue`s."""

from dataclasses import dataclass, field
from typing import Any

from streamwright.core.validation import Issue

ERROR = "error"
WARNING = "warning"


@dataclass
class Report:
    kind: str
    valid: bool
    issues: list[Issue] = field(default_factory=list)
    subject: dict[str, Any] | None = None
    plan: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == ERROR]

    @property
    def warnings(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == WARNING]

    @property
    def summary(self) -> str:
        name = (self.subject or {}).get("name") or (self.subject or {}).get("path") or "input"
        errors, warnings = len(self.errors), len(self.warnings)
        if self.valid:
            tail = f" with {warnings} warning(s)" if warnings else " with no errors or warnings"
            return f"Valid: {self.kind} '{name}'{tail}."
        return f"Invalid: {self.kind} '{name}' has {errors} error(s) and {warnings} warning(s)."

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "valid": self.valid,
            "summary": self.summary,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
            "notes": list(self.notes),
            "subject": self.subject,
            "plan": self.plan,
        }


def failure(kind: str, code: str, message: str, file: str | None = None) -> Report:
    """A report for input that could not be checked at all (a path outside the workspace, a bad argument)."""
    return Report(kind, False, [Issue(ERROR, code, message, file)])
