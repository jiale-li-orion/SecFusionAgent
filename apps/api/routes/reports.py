from base64 import b64encode
from hashlib import sha256
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from packages.reasoning.report_html import REPORT_CSS, report_etag

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def html_report_response(html: str) -> HTMLResponse:
    style_hash = b64encode(sha256(REPORT_CSS.encode()).digest()).decode()
    return HTMLResponse(
        html,
        headers={
            "Content-Security-Policy": (
                "default-src 'none'; script-src 'none'; "
                f"style-src 'sha256-{style_hash}'; font-src 'self'; "
                "base-uri 'none'; form-action 'none'; frame-ancestors 'self'; object-src 'none'"
            ),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "ETag": report_etag(html),
        },
    )


@router.get("/fonts/{weight}.woff2", include_in_schema=False)
def report_font(weight: Literal["regular", "bold"]) -> FileResponse:
    # Product font assets are already bundled and licensed in this repository.
    name = "NotoSansSC-UI-" + ("Regular" if weight == "regular" else "Bold") + ".woff2"
    path = Path(__file__).resolve().parents[2] / "web" / "src" / "assets" / "fonts" / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="report font unavailable")
    return FileResponse(
        path,
        media_type="font/woff2",
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Content-Type-Options": "nosniff",
        },
    )
