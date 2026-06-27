"""Terminal and JSON rendering for issue search results."""

from __future__ import annotations

import json
from typing import Any, TextIO

from .client import SearchResult


def repository_name(item: dict[str, Any]) -> str:
    repository_url = str(item.get("repository_url", ""))
    marker = "/repos/"
    if marker in repository_url:
        return repository_url.split(marker, 1)[1]
    return "unknown repository"


def normalized_issue(item: dict[str, Any]) -> dict[str, Any]:
    labels = item.get("labels", [])
    label_names = [
        str(label.get("name"))
        for label in labels
        if isinstance(label, dict) and label.get("name") is not None
    ]
    assignees = item.get("assignees", [])
    assignee_names = [
        str(assignee.get("login"))
        for assignee in assignees
        if isinstance(assignee, dict) and assignee.get("login") is not None
    ]
    return {
        "repository": repository_name(item),
        "number": item.get("number"),
        "title": item.get("title"),
        "url": item.get("html_url"),
        "labels": label_names,
        "state": item.get("state"),
        "comments": item.get("comments", 0),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "assignees": assignee_names,
    }


def write_json(result: SearchResult, stream: TextIO) -> None:
    payload = {
        "query": result.query,
        "total_count": result.total_count,
        "incomplete_results": result.incomplete_results,
        "items": [normalized_issue(item) for item in result.items],
    }
    json.dump(payload, stream, indent=2)
    stream.write("\n")


def write_text(result: SearchResult, stream: TextIO) -> None:
    shown = len(result.items)
    stream.write(f"Found {result.total_count} matching issues; showing {shown}.\n")
    if result.incomplete_results:
        stream.write("Warning: GitHub marked these search results as incomplete.\n")
    if not result.items:
        return

    for index, item in enumerate(result.items, start=1):
        issue = normalized_issue(item)
        labels = ", ".join(issue["labels"]) or "none"
        assignees = ", ".join(issue["assignees"]) or "unassigned"
        stream.write(
            f"\n{index}. {issue['repository']}#{issue['number']} — {issue['title']}\n"
            f"   labels: {labels} | assignees: {assignees} | comments: {issue['comments']}\n"
            f"   updated: {issue['updated_at']}\n"
            f"   {issue['url']}\n"
        )
