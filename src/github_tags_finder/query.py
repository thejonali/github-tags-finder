"""Build GitHub issue search queries from structured CLI filters."""

from __future__ import annotations

from dataclasses import dataclass, field


DEFAULT_LABELS = ("good first issue", "help wanted")


def quote(value: str) -> str:
    """Quote a GitHub search value without changing its meaning."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


@dataclass(frozen=True)
class SearchFilters:
    terms: tuple[str, ...] = ()
    state: str = "open"
    language: str | None = None
    labels: tuple[str, ...] = DEFAULT_LABELS
    match_labels: str = "any"
    repositories: tuple[str, ...] = ()
    organization: str | None = None
    user: str | None = None
    assignee: str | None = None
    no_assignee: bool = False
    created: str | None = None
    updated: str | None = None
    include_archived: bool = False
    qualifiers: tuple[str, ...] = field(default_factory=tuple)

    def build(self) -> str:
        if self.state not in {"open", "closed", "all"}:
            raise ValueError(f"Unsupported state: {self.state}")
        if self.match_labels not in {"any", "all"}:
            raise ValueError(f"Unsupported label matching mode: {self.match_labels}")
        if self.assignee and self.no_assignee:
            raise ValueError("assignee and no_assignee cannot be used together")

        parts = [*self.terms, "is:issue"]
        if self.state != "all":
            parts.append(f"is:{self.state}")
        if not self.include_archived:
            parts.append("archived:false")
        if self.language:
            parts.append(f"language:{quote(self.language)}")
        parts.extend(self._label_parts())
        parts.extend(self._repository_parts())
        if self.organization:
            parts.append(f"org:{quote(self.organization)}")
        if self.user:
            parts.append(f"user:{quote(self.user)}")
        if self.assignee:
            parts.append(f"assignee:{quote(self.assignee)}")
        elif self.no_assignee:
            parts.append("no:assignee")
        if self.created:
            parts.append(f"created:{self.created}")
        if self.updated:
            parts.append(f"updated:{self.updated}")
        parts.extend(
            qualifier.strip() for qualifier in self.qualifiers if qualifier.strip()
        )
        return " ".join(parts)

    def _label_parts(self) -> list[str]:
        if not self.labels:
            return []
        if self.match_labels == "all":
            return [f"label:{quote(label)}" for label in self.labels]
        values = ",".join(quote(label) for label in self.labels)
        return [f"label:{values}"]

    def _repository_parts(self) -> list[str]:
        if not self.repositories:
            return []
        qualifiers = [f"repo:{quote(repo)}" for repo in self.repositories]
        if len(qualifiers) == 1:
            return qualifiers
        return [f"({' OR '.join(qualifiers)})"]
