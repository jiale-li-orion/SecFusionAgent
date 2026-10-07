"""Check persisted Decision -> citation -> Evidence -> refresh without model calls."""

from __future__ import annotations

import argparse
from urllib.parse import urlencode

import httpx
from playwright.sync_api import expect, sync_playwright


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--product-base", default="http://127.0.0.1:8000/product")
    args = parser.parse_args()
    with httpx.Client(base_url=args.api_base, trust_env=False, timeout=20) as client:
        response = client.get("/api/v1/investigations?limit=48")
        response.raise_for_status()
        decision = next(
            (
                item["latest_decision"]
                for item in response.json()["items"]
                if (item.get("latest_decision") or {}).get("citations")
            ),
            None,
        )
    if decision is None:
        raise RuntimeError("No persisted cited Decision available; this gate does not create one.")
    # Deliberately omit a target: generic RETRIEVE citations must still be inspectable.
    query = urlencode({"decision": decision["decision_id"], "profile": "RETRIEVE"})
    url = f"{args.product_base.rstrip('/')}/start?{query}"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width, height in ((1440, 1000), (390, 844)):
            page = browser.new_page(
                viewport={"width": width, "height": height}, reduced_motion="reduce"
            )
            errors: list[str] = []
            posts: list[str] = []
            page.on("pageerror", lambda error, target=errors: target.append(str(error)))
            page.on(
                "request",
                lambda request, target=posts: (
                    target.append(request.url) if request.method == "POST" else None
                ),
            )
            page.goto(url, wait_until="domcontentloaded")
            report = page.locator(".decision-report")
            expect(report).to_be_visible(timeout=20_000)
            assert report.bounding_box()["width"] >= min(width - 100, 600), (
                "Decision report is squeezed by the surrounding layout"
            )
            for conclusion in decision["conclusions"]:
                expect(report).to_contain_text(conclusion["statement"])
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2"), (
                "Horizontal overflow"
            )
            citation = page.locator(".decision-report-citations button").first
            citation.click()
            expect(page.get_by_role("dialog")).to_be_visible()
            expect(page.locator(".trace-hero")).to_be_visible(timeout=15_000)
            page.keyboard.press("Escape")
            expect(page.get_by_role("dialog")).to_have_count(0)
            assert citation.evaluate("e => document.activeElement === e"), (
                "Citation focus was not restored"
            )
            page.reload(wait_until="domcontentloaded")
            expect(report).to_be_visible(timeout=20_000)
            assert not posts, f"Read/refresh created commands: {posts}"
            assert not errors, errors
            print(f"PASS · {width}px · persisted answer / target-free citation / Escape / refresh")
            page.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
