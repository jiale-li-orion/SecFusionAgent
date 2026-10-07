from __future__ import annotations

import argparse
from dataclasses import dataclass

from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


@dataclass(frozen=True, slots=True)
class Surface:
    name: str
    path: str
    root: str


SURFACES = (
    Surface("world", "/", ".world-space"),
    Surface("start", "/start", ".start-space"),
    Surface("intelligence", "/intelligence", ".intelligence-space"),
    Surface("investigations", "/investigations", ".investigations-space"),
    Surface("agents", "/agents", ".agents-space"),
    Surface("observatory", "/observatory", ".observatory-space"),
)


def _url(base: str, path: str) -> str:
    return f"{base.rstrip('/')}{path}"


def _visible_hit_failures(page: Page) -> list[str]:
    return page.evaluate(
        """() => {
          const selector = [
            'button:not([disabled])',
            'a[href]',
            'input:not([disabled])',
            'textarea:not([disabled])',
          ].join(', ');
          const failures = [];
          for (const node of document.querySelectorAll(selector)) {
            const style = getComputedStyle(node);
            const rect = node.getBoundingClientRect();
            if (
              style.visibility === 'hidden'
              || style.display === 'none'
              || Number(style.opacity) < 0.02
            ) continue;
            if (
              rect.width < 8
              || rect.height < 8
              || rect.bottom <= 0
              || rect.right <= 0
              || rect.top >= innerHeight
              || rect.left >= innerWidth
            ) continue;
            const x = Math.max(1, Math.min(innerWidth - 2, rect.left + rect.width / 2));
            const y = Math.max(1, Math.min(innerHeight - 2, rect.top + rect.height / 2));
            const hit = document.elementFromPoint(x, y);
            if (!hit || (hit !== node && !node.contains(hit))) {
              failures.push({
                target: node.className
                  || node.getAttribute('aria-label')
                  || node.textContent?.trim().slice(0, 48)
                  || node.tagName,
                hit: hit?.className || hit?.tagName || 'none',
                x: Math.round(x),
                y: Math.round(y),
              });
            }
          }
          return failures.map((item) => `${item.target} @ ${item.x},${item.y} <- ${item.hit}`);
        }"""
    )


def _check_stateful_controls(page: Page, surface: Surface) -> list[str]:
    errors: list[str] = []
    if surface.name == "world":
        lens = page.locator(".world-time-lens button")
        if lens.count() >= 2:
            lens.nth(1).click()
            if "active" not in (lens.nth(1).get_attribute("class") or ""):
                errors.append("WORLD time-window control did not become active")

    if surface.name == "start":
        modes = page.locator(".mode-chamber")
        for index in range(modes.count()):
            mode = modes.nth(index)
            mode.click()
            if mode.get_attribute("aria-pressed") != "true":
                errors.append(f"START mode {index + 1} did not become selected")
        advanced = page.locator(".advanced-toggle")
        if advanced.count():
            advanced.click()
            if page.locator(".mission-advanced").count() == 0:
                errors.append("START advanced controls did not open")

    if surface.name == "observatory":
        switches = page.locator(".observatory-mode-switch button")
        if switches.count() >= 2:
            try:
                switches.nth(1).click(timeout=2_000)
                page.wait_for_timeout(120)
                class_name = page.locator(".observatory-space").get_attribute("class") or ""
                if "observatory-proof" not in class_name:
                    errors.append("OBSERVATORY proof switch did not change mode")
            except PlaywrightTimeoutError as exc:
                reason = exc.message.splitlines()[-1]
                errors.append(f"OBSERVATORY proof switch is not clickable: {reason}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-base", default="http://127.0.0.1:8000/product")
    args = parser.parse_args()
    failures: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for surface in SURFACES:
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(
                _url(args.product_base, surface.path),
                wait_until="domcontentloaded",
                timeout=20_000,
            )
            page.locator(surface.root).first.wait_for(state="visible", timeout=10_000)
            page.wait_for_timeout(500)
            page_failures = _visible_hit_failures(page)
            page_failures.extend(_check_stateful_controls(page, surface))
            if page_failures:
                failures.extend(f"{surface.name}: {failure}" for failure in page_failures)
                print(f"FAIL · {surface.name} · {len(page_failures)} interaction issue(s)")
            else:
                print(f"PASS · {surface.name}")
            page.close()
        browser.close()

    if failures:
        print("\n".join(failures))
        return 1
    print("PRODUCT INTERACTION GATE PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
