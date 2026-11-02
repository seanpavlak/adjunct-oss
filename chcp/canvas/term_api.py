"""Canvas JSON reads for term setup, using the logged-in browser cookies."""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urlencode

from chcp.core.term_setup import TermSetupError
from chcp.settings import canvas_config

_NEXT_LINK = re.compile(r"<([^>]+)>\s*;\s*rel=\"next\"")


def favorites_url() -> str:
    query = urlencode(
        [
            ("include[]", "term"),
            ("include[]", "sections"),
            ("sort", "nickname"),
        ]
    )
    return f"{canvas_config.BASE_URL}/api/v1/users/self/favorites/courses?{query}"


def course_url(course_id: str) -> str:
    return f"{canvas_config.BASE_URL}/api/v1/courses/{course_id}"


def modules_url(course_id: str) -> str:
    query = urlencode([("include[]", "items"), ("per_page", "100")])
    return f"{canvas_config.BASE_URL}/api/v1/courses/{course_id}/modules?{query}"


def discussions_url(course_id: str) -> str:
    query = urlencode(
        [
            ("exclude_assignment_descriptions", "true"),
            ("exclude_context_module_locked_topics", "true"),
            ("include[]", "sections_user_count"),
            ("include[]", "sections"),
            ("include_assignment", "true"),
            ("page", "1"),
            ("per_page", "100"),
            ("plain_messages", "true"),
        ]
    )
    return f"{canvas_config.BASE_URL}/api/v1/courses/{course_id}/discussion_topics?{query}"


def topic_url(course_id: str, topic_id: str) -> str:
    query = urlencode(
        [
            ("include_assignment", "true"),
            ("plain_messages", "true"),
        ]
    )
    return (
        f"{canvas_config.BASE_URL}/api/v1/courses/{course_id}"
        f"/discussion_topics/{topic_id}?{query}"
    )


def next_link(header: Optional[str]) -> Optional[str]:
    """URL from a Canvas Link header rel=next, if present."""
    if not header:
        return None
    for part in header.split(","):
        match = _NEXT_LINK.search(part.strip())
        if match:
            return match.group(1)
    return None


def fetch_favorites(request: Any) -> list[dict[str, Any]]:
    return get_json_list(request, favorites_url())


def fetch_term_payload(request: Any, course_id: str) -> dict[str, Any]:
    """Course, modules, and discussions. Missing topics are fetched one by one."""
    course = get_json(request, course_url(course_id))
    modules = get_json_list(request, modules_url(course_id))
    discussions = get_json_list(request, discussions_url(course_id))
    known = {str(topic.get("id")) for topic in discussions if topic.get("id") is not None}
    for module in modules:
        for item in module.get("items") or []:
            if str(item.get("type") or "") != "Discussion":
                continue
            content_id = item.get("content_id")
            if content_id is None or str(content_id) in known:
                continue
            topic = get_json(request, topic_url(course_id, str(content_id)))
            discussions.append(topic)
            if topic.get("id") is not None:
                known.add(str(topic.get("id")))
    return {"course": course, "modules": modules, "discussions": discussions}


def get_json(request: Any, url: str) -> Any:
    response = request.get(url, headers={"Accept": "application/json"})
    return _read(response, url)


def get_json_list(request: Any, url: str) -> list:
    items: list = []
    next_url: Optional[str] = url
    while next_url:
        response = request.get(next_url, headers={"Accept": "application/json"})
        payload = _read(response, next_url)
        if not isinstance(payload, list):
            raise TermSetupError(f"Expected a list from {next_url}")
        items.extend(payload)
        header = _header(response, "link")
        next_url = next_link(header)
    return items


def _header(response: Any, name: str) -> Optional[str]:
    headers = getattr(response, "headers", None) or {}
    if hasattr(headers, "get"):
        return headers.get(name)
    return None


def _read(response: Any, url: str) -> Any:
    status = getattr(response, "status", None)
    if status in (401, 403):
        raise TermSetupError(f"Canvas refused {url} ({status}). The session may have expired.")
    if status is not None and status >= 400:
        detail = _error_detail(response)
        message = f"Canvas API {status} for {url}"
        if detail:
            message = f"{message}: {detail}"
        raise TermSetupError(message)
    try:
        return response.json()
    except Exception as exc:
        raise TermSetupError(
            "Canvas returned a page that is not JSON. The session may have expired."
        ) from exc


def _error_detail(response: Any) -> str:
    try:
        body = response.json()
    except Exception:
        return ""
    if isinstance(body, dict) and body.get("errors"):
        first = body["errors"][0]
        if isinstance(first, dict):
            return str(first.get("message") or "")
    return ""
