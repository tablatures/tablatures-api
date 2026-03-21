
import html
import re
from flask import request


def sanitize_string(value: str, max_length: int = 200) -> str:
    """Sanitize a string input by stripping dangerous characters and limiting length."""
    value = value[:max_length].strip()
    # Remove control characters but keep normal unicode
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)
    return value


def escape_for_html(value: str) -> str:
    """Escape a string for safe rendering in HTML contexts."""
    return html.escape(value, quote=True)


def parse_pagination_params(
    default_page: int = 1,
    default_limit: int = 50,
    max_limit: int = 100,
    min_limit: int = 1,
) -> tuple:
    """Parse and clamp page/limit query parameters from the current request.

    Returns:
        (page, limit) tuple with values clamped to valid ranges.
    """
    try:
        page = max(int(request.args.get('page', default_page)), 1)
    except (ValueError, TypeError):
        page = default_page

    try:
        limit = min(max(int(request.args.get('limit', default_limit)), min_limit), max_limit)
    except (ValueError, TypeError):
        limit = default_limit

    return page, limit
