from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request

from playwright.sync_api import Browser, Page, sync_playwright

if TYPE_CHECKING:
    from scripts.product_check_session import (
        open_product_request,
        product_session_cookie,
        request_headers,
    )
elif __package__:
    from .product_check_session import open_product_request, product_session_cookie, request_headers
else:
    from product_check_session import open_product_request, product_session_cookie, request_headers


@dataclass(frozen=True, slots=True)
class Viewport:
    name: str
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class Landmark:
    selector: str
    desktop_ratio: float
    compact_ratio: float


@dataclass(frozen=True, slots=True)
class ProductSpace:
    name: str
    path: str
    root_selector: str
    landmarks: tuple[Landmark, ...]


VIEWPORTS = (
    Viewport("desktop", 1440, 1000),
    Viewport("projector", 1366, 768),
    Viewport("tablet", 1024, 768),
    Viewport("mobile", 390, 844),
)


def _json(base_url: str, path: str, *, cookie: str | None = None) -> dict[str, Any]:
    request = Request(
        f"{base_url.rstrip('/')}{path}", headers=request_headers("application/json", cookie)
    )
    try:
        with open_product_request(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"visual gate data read failed for {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"visual gate expected object payload from {path}")
    return payload


def _first_dict(payload: dict[str, Any], key: str) -> dict[str, Any] | None:
    values = payload.get(key)
    if not isinstance(values, list):
        return None
    return next((item for item in values if isinstance(item, dict)), None)


def _query(path: str, **params: str) -> str:
    return f"{path}?{urlencode(params)}" if params else path


def _resolve_spaces(api_base: str, cookie: str | None = None) -> tuple[ProductSpace, ...]:
    hot = _json(api_base, "/api/v1/world/hot?limit=8")
    cases = _json(api_base, "/api/v1/investigations?limit=8", cookie=cookie) if cookie else {}
    agents = _json(api_base, "/api/v1/agents/runtime?task_limit=8", cookie=cookie) if cookie else {}

    hot_item = next(
        (
            item
            for item in hot.get("items", [])
            if isinstance(item, dict) and isinstance(item.get("cve_id"), str)
        ),
        None,
    )
    case = _first_dict(cases, "items")
    task = _first_dict(agents, "recent_tasks")

    cve = str(hot_item["cve_id"]) if hot_item else ""
    case_id = str(case["case_id"]) if case and case.get("case_id") else ""
    run_id = str(task["run_id"]) if task and task.get("run_id") else ""
    targets = case.get("target_object_ids", []) if case else []
    canonical_object = str(targets[0]) if targets else ""

    spaces = (
        ProductSpace(
            "world",
            "/",
            ".evidence-world",
            (
                Landmark(".studio-heading", 0.78, 0.82),
                Landmark(".ew-foreground", 0.42, 0.42),
                Landmark(".ew-composition", 0.78, 0.82),
            ),
        ),
        ProductSpace(
            "start",
            _query("/start", profile="VERIFY", cve=cve) if cve else "/start",
            ".start-space",
            (
                Landmark(".studio-heading", 0.42, 0.82),
                Landmark(".vision-start-desk", 0.48, 0.82),
                Landmark(".payload-deck", 0.24, 0.82),
            ),
        ),
        ProductSpace(
            "intelligence",
            _query("/intelligence", object=canonical_object)
            if canonical_object
            else "/intelligence",
            ".intelligence-space",
            (
                Landmark(".studio-heading", 0.62, 0.82),
                Landmark(".intel-layout", 0.76, 0.82),
                Landmark(".intel-main", 0.48, 0.82),
            ),
        ),
        ProductSpace(
            "investigations",
            _query("/investigations", case=case_id) if case_id else "/investigations",
            ".investigations-space",
            (
                Landmark(".investigation-layout", 0.76, 0.82),
                *((Landmark(".case-workspace", 0.42, 0.82),) if case_id else ()),
            ),
        ),
        ProductSpace(
            "agents",
            _query("/agents", run=run_id) if run_id else "/agents",
            ".agents-space",
            (
                Landmark(".studio-heading", 0.72, 0.82),
                Landmark(".agent-runtime-grid", 0.72, 0.82),
            ),
        ),
        ProductSpace(
            "observatory",
            "/observatory",
            ".observatory-space",
            (
                Landmark(".live-command-strip", 0.68, 0.82),
                Landmark(".observatory-live-grid", 0.72, 0.82),
            ),
        ),
    )

    return tuple(
        space
        for space in spaces
        if cookie or space.name not in {"start", "investigations", "agents"}
    )


def _join_product_url(product_base: str, path: str) -> str:
    return f"{product_base.rstrip('/')}{path}"


def _box_width(page: Page, selector: str) -> float | None:
    locator = page.locator(selector).first
    if locator.count() == 0 or not locator.is_visible():
        return None
    box = locator.bounding_box()
    return None if box is None else float(box["width"])


def _check_page(
    page: Page,
    *,
    space: ProductSpace,
    viewport: Viewport,
    product_base: str,
    screenshot_dir: Path,
) -> list[str]:
    errors: list[str] = []
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.goto(
        _join_product_url(product_base, space.path),
        wait_until="domcontentloaded",
        timeout=20_000,
    )
    page.locator(space.root_selector).first.wait_for(state="visible", timeout=10_000)
    page.wait_for_timeout(900)

    metrics = page.evaluate(
        """() => ({
          innerWidth: window.innerWidth,
          documentWidth: document.documentElement.scrollWidth,
          bodyWidth: document.body.scrollWidth,
          mainWidth: document.querySelector('#product-main')?.getBoundingClientRect().width ?? 0,
        })"""
    )
    inner_width = float(metrics["innerWidth"])
    document_width = float(metrics["documentWidth"])
    body_width = float(metrics["bodyWidth"])
    main_width = float(metrics["mainWidth"])
    if max(document_width, body_width) > inner_width + 3:
        errors.append(
            f"document overflow {max(document_width, body_width):.0f}px > {inner_width:.0f}px"
        )
    if main_width < max(280, inner_width * 0.68):
        errors.append(f"product main collapsed to {main_width:.0f}px")

    if space.name == "world":
        try:
            page.locator(".ew-story").wait_for(state="visible", timeout=8_000)
        except Exception:
            errors.append("WORLD did not render a real source story")

    compact = viewport.width <= 1100
    for landmark in space.landmarks:
        width = _box_width(page, landmark.selector)
        if width is None:
            errors.append(f"{landmark.selector} missing or hidden")
            continue
        ratio = landmark.compact_ratio if compact else landmark.desktop_ratio
        minimum = min(main_width * ratio, max(280, inner_width - 48))
        if width + 2 < minimum:
            errors.append(
                f"{landmark.selector} collapsed to {width:.0f}px; expected >= {minimum:.0f}px"
            )

    errors.extend(f"page error: {message}" for message in page_errors)
    page.screenshot(
        path=str(screenshot_dir / f"{viewport.name}-{space.name}.png"),
        full_page=False,
        animations="disabled",
        timeout=15_000,
    )
    return errors


def _check_live_observatory(
    browser: Browser,
    product_base: str,
    screenshot_dir: Path,
) -> list[str]:
    errors: list[str] = []
    space = ProductSpace(
        "observatory-live",
        "/observatory",
        ".observatory-space",
        (
            Landmark(".live-command-strip", 0.68, 0.82),
            Landmark(".telemetry-wide", 0.48, 0.82),
            Landmark(".system-status-panel", 0.24, 0.82),
        ),
    )
    for viewport in (VIEWPORTS[0], VIEWPORTS[-1]):
        context = browser.new_context(viewport={"width": viewport.width, "height": viewport.height})
        page = context.new_page()
        try:
            errors.extend(
                f"{viewport.name}: {error}"
                for error in _check_page(
                    page,
                    space=space,
                    viewport=viewport,
                    product_base=product_base,
                    screenshot_dir=screenshot_dir,
                )
            )
            if page.locator(".telemetry-chart").count() < 5:
                errors.append(f"{viewport.name}: full live measurement chart set missing")
            if page.locator(".world-measurement-ledger > div").count() != 6:
                errors.append(f"{viewport.name}: measurement ledger is incomplete")
        finally:
            context.close()
    return errors


def _check_reduced_motion(browser: Browser, product_base: str, screenshot_dir: Path) -> list[str]:
    context = browser.new_context(
        viewport={"width": 1440, "height": 1000},
        reduced_motion="reduce",
    )
    page = context.new_page()
    errors: list[str] = []
    try:
        page.goto(
            _join_product_url(product_base, "/"),
            wait_until="domcontentloaded",
            timeout=20_000,
        )
        page.locator(".evidence-world").first.wait_for(state="visible", timeout=10_000)
        page.wait_for_timeout(500)
        if page.locator(".vision-orbits").count() == 0:
            errors.append("reduced-motion WORLD did not expose the SVG world")
        if page.locator(".route-aperture").count() != 0:
            errors.append("reduced-motion route still rendered cinematic aperture motion")
        page.screenshot(path=str(screenshot_dir / "reduced-motion-world.png"), full_page=False)
    finally:
        context.close()
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Browser-level Product composition regression gate",
        epilog="SECFUSION_PRODUCT_SESSION_COOKIE enables private spaces; missing accounts skip.",
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--product-base", default="http://127.0.0.1:8000/product")
    parser.add_argument(
        "--screenshots-dir",
        type=Path,
        default=Path("/tmp/secfusion-product-visual"),
    )
    args = parser.parse_args()

    args.screenshots_dir.mkdir(parents=True, exist_ok=True)
    cookie = product_session_cookie()
    if (
        cookie is not None
        and _json(args.api_base, "/api/v1/auth/me", cookie=cookie).get("authenticated") is not True
    ):
        raise RuntimeError("configured Product session is expired or unauthenticated")
    spaces = _resolve_spaces(args.api_base, cookie)
    skipped = [] if cookie else ["start", "investigations", "agents"]
    for name in skipped:
        print(f"SKIP · {name} · no Product account session supplied")
    failures: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for viewport in VIEWPORTS:
                context = browser.new_context(
                    viewport={"width": viewport.width, "height": viewport.height}
                )
                if cookie is not None:
                    origin = urlsplit(args.product_base)
                    context.add_cookies(
                        [
                            {
                                "name": "secfusion_session",
                                "value": cookie.partition("=")[2],
                                "url": f"{origin.scheme}://{origin.netloc}/",
                                "httpOnly": True,
                                "secure": origin.scheme == "https",
                                "sameSite": "Lax",
                            }
                        ]
                    )
                page = context.new_page()
                try:
                    for space in spaces:
                        errors = _check_page(
                            page,
                            space=space,
                            viewport=viewport,
                            product_base=args.product_base,
                            screenshot_dir=args.screenshots_dir,
                        )
                        if errors:
                            failures.extend(
                                f"{viewport.name}/{space.name}: {error}" for error in errors
                            )
                        else:
                            print(
                                f"PASS · {viewport.name:9s} · {space.name:14s} · "
                                f"{viewport.width}x{viewport.height}"
                            )
                finally:
                    context.close()
            failures.extend(
                f"reduced-motion/world: {error}"
                for error in _check_reduced_motion(
                    browser,
                    args.product_base,
                    args.screenshots_dir,
                )
            )
            failures.extend(
                f"observatory-live: {error}"
                for error in _check_live_observatory(
                    browser,
                    args.product_base,
                    args.screenshots_dir,
                )
            )
        finally:
            browser.close()

    if failures:
        print("PRODUCT VISUAL GATE FAIL")
        for failure in failures:
            print(f"FAIL · {failure}")
        return 1
    outcome = "COMPLETE" if skipped else "PASS"
    print(
        f"PRODUCT VISUAL GATE {outcome} · {len(spaces)} spaces checked · "
        f"{len(skipped)} skipped · screenshots: {args.screenshots_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
