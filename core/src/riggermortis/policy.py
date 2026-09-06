"""Content policy: enforced in the engine core, not in any frontend.

Because the add-on and the MCP server are thin shells over this module, no
frontend can bypass it. The public shape is deliberately boring:

* the default build is SFW;
* an opt-in adult module (off by default, requires explicit confirmation)
  permits explicit content of *fictional adult characters only*;
* hard lines never toggle: no minors, no explicit content of real
  identifiable people, nothing illegal. See docs/POLICY.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import PolicyError

#: Stable, documented refusal codes — part of the public API surface
#: (add-on reports and MCP structured errors both use these).
MINOR_CONTENT = "minor_content_prohibited"
REAL_PERSON_EXPLICIT = "real_person_explicit_prohibited"
ADULT_MODULE_DISABLED = "adult_module_disabled"
INVALID_REQUEST = "invalid_request"

HARD_LINES = [
    "no sexual content involving minors, regardless of fictional framing",
    "no explicit content of real, identifiable people",
    "no content illegal in the user's jurisdiction",
]


class ContentCategory(str, Enum):
    MINOR = "minor"
    REAL_PERSON = "real_person"
    FICTIONAL_ADULT = "fictional_adult"
    OTHER = "other"


@dataclass(frozen=True)
class Refusal:
    """A structured, documented refusal. Also the MCP error shape."""

    code: str
    message: str
    category: ContentCategory
    retryable: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "category": self.category.value,
            "retryable": self.retryable,
        }


class PolicyEngine:
    """Owns the adult-module flag and evaluates requests against the policy."""

    def __init__(self, adult_module_enabled: bool = False) -> None:
        if adult_module_enabled:
            raise PolicyError(
                "PolicyEngine cannot be constructed with the adult module enabled",
                hint="call enable_adult_module(confirm=True) on a default instance",
            )
        self._adult_module_enabled = False

    # -- configuration -------------------------------------------------------

    @property
    def adult_module_enabled(self) -> bool:
        return self._adult_module_enabled

    def enable_adult_module(self, confirm: bool) -> None:
        if confirm is not True:
            raise PolicyError(
                "enabling the adult module requires explicit confirmation",
                hint="call enable_adult_module(confirm=True) after showing the user the policy notice",
            )
        self._adult_module_enabled = True

    def disable_adult_module(self) -> None:
        self._adult_module_enabled = False

    def status(self) -> dict[str, object]:
        return {
            "adult_module_enabled": self._adult_module_enabled,
            "defaults": {"adult_module_enabled": False},
            "hard_lines": list(HARD_LINES),
            "policy_doc": "docs/POLICY.md",
        }

    # -- evaluation ------------------------------------------------------------

    def check_explicit_request(self, subject: str) -> Refusal | None:
        """Evaluate a request for explicit content.

        ``subject`` is one of: ``minor``, ``real_person``, ``fictional_adult``,
        ``other``. Minors and real people refuse unconditionally; fictional
        adults refuse unless the adult module is enabled.
        """
        if subject == "minor":
            return Refusal(
                code=MINOR_CONTENT,
                message=(
                    "Sexual content involving minors is never permitted, regardless of "
                    "fictional framing. This is a hard line and cannot be toggled."
                ),
                category=ContentCategory.MINOR,
            )
        if subject == "real_person":
            return Refusal(
                code=REAL_PERSON_EXPLICIT,
                message=(
                    "Explicit content of real, identifiable people is not permitted. "
                    "There is no photo-to-explicit pipeline in this engine, by design."
                ),
                category=ContentCategory.REAL_PERSON,
            )
        if subject == "fictional_adult":
            if self._adult_module_enabled:
                return None
            return Refusal(
                code=ADULT_MODULE_DISABLED,
                message=(
                    "The adult module is off by default. Enable it in preferences with "
                    "explicit confirmation to allow explicit content of fictional adult characters."
                ),
                category=ContentCategory.FICTIONAL_ADULT,
                retryable=True,
            )
        if subject == "other":
            return None
        return Refusal(
            code=INVALID_REQUEST,
            message=f"unknown content subject {subject!r} (expected: minor, real_person, fictional_adult, other)",
            category=ContentCategory.OTHER,
        )
