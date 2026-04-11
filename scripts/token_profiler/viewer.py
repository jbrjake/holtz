"""Generate self-contained HTML viewer from template + RunProfile data."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from token_profiler.models import RunProfile

TEMPLATE_PATH = Path(__file__).parent / "viewer_template.html"
DATA_PLACEHOLDER = "/* __PROFILE_DATA_PLACEHOLDER__ */"


def generate_html(profile: RunProfile) -> str:
    """Inject RunProfile JSON into the HTML template."""
    template = TEMPLATE_PATH.read_text()
    data = asdict(profile)
    profile_json = json.dumps(data, default=str)  # str handles datetimes
    # Escape </script> to prevent XSS when embedding in <script> tags
    profile_json = profile_json.replace("</", r"<\/")
    return template.replace(
        DATA_PLACEHOLDER, f"const PROFILE_DATA = {profile_json};"
    )
