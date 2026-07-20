"""Public-source crawl collector: render pages with Playwright, optionally accept
consent, capture network beacons, and produce a normalized Snapshot.

Pure signal extraction lives in `signals.py` so it can be unit-tested without a
browser. This module handles browser orchestration and HTTP fetching only.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

import httpx

from core.collectors.gtm_container import parse_container
from core.collectors.signals import (
    GTM_SNIPPET,
    _normalize_url,
    discover_links,
    extract_signals,
    merge_signals,
)
from core.models.snapshot import Snapshot
from core.schemas import loader

USER_AGENT = "AdwizeAuditBot/0.1 (+https://getadwize.com)"


async def fetch_gtm_container(container_id: str, timeout: float = 10.0) -> dict[str, Any]:
    url = f"https://www.googletagmanager.com/gtm.js?id={container_id}"
    empty = {"parsed": False, "id": container_id, "tags": [], "tag_count": 0}
    try:
        async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return empty
            return parse_container(resp.text, container_id)
    except httpx.HTTPError:
        return empty


def _cmp_schema() -> dict[str, Any]:
    return loader.load("cmp")


async def _accept_consent(page) -> dict[str, Any]:
    """Best-effort click of an 'accept all' control for a known/textual CMP.
    Returns {accepted, cmp}. Never raises — consent UIs are messy."""
    schema = _cmp_schema()
    for cmp in schema.get("cmps", []):
        for sel in cmp.get("accept_selectors", []):
            try:
                loc = page.locator(sel).first
                if await loc.count() > 0:
                    await loc.click(timeout=3000)
                    return {"accepted": True, "cmp": cmp["name"]}
            except Exception:  # noqa: BLE001
                continue
    for text in schema.get("generic_accept_texts", []):
        try:
            loc = page.get_by_role("button", name=re.compile(re.escape(text), re.IGNORECASE)).first
            if await loc.count() > 0:
                await loc.click(timeout=3000)
                return {"accepted": True, "cmp": "generic"}
        except Exception:  # noqa: BLE001
            continue
    return {"accepted": False, "cmp": None}


async def _scrape(context, url: str, timeout: float, accept_consent: bool) -> dict[str, Any]:
    """Render one page in an existing browser context, optionally accepting
    consent, and return a raw observation (html + requests + cookies + consent)."""
    request_urls: list[str] = []
    consent = {"accepted": False, "cmp": None}
    page = await context.new_page()
    try:
        page.on("request", lambda req: request_urls.append(req.url))
        response = await page.goto(url, wait_until="networkidle", timeout=int(timeout * 1000))
        status = response.status if response else 0
        if accept_consent:
            consent = await _accept_consent(page)
            if consent["accepted"]:
                try:
                    await page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:  # noqa: BLE001
                    pass
        html = await page.content()
        # Detect the dataLayer at runtime: GTM creates it via `w[l]=w[l]||[]`
        # (referenced by variable, not by name), so a static HTML regex misses it.
        try:
            dl_len = await page.evaluate(
                "() => Array.isArray(window.dataLayer) ? window.dataLayer.length : -1"
            )
        except Exception:  # noqa: BLE001 — page may navigate/close; treat as unknown
            dl_len = -1
        site_host = urlsplit(url).netloc.removeprefix("www.")
        cookies = [
            {
                "name": c.get("name"),
                "domain": c.get("domain"),
                "first_party": site_host in (c.get("domain") or ""),
            }
            for c in await context.cookies()
        ]
        return {
            "url": url,
            "http_status": status,
            "html": html,
            "request_urls": request_urls,
            "cookies": cookies,
            "consent": consent,
            "datalayer_runtime": {"exists": dl_len >= 0, "length": max(int(dl_len), 0)},
        }
    finally:
        await page.close()


async def collect(
    url: str,
    timeout: float = 20.0,
    extra_containers: list[str] | None = None,
    accept_consent: bool = True,
    max_pages: int = 1,
    extra_pages: list[str] | None = None,
) -> Snapshot:
    """Crawl a site (homepage + up to `max_pages`-1 discovered internal pages),
    accept consent on each, discover + fetch every GTM container seen across all
    pages and network requests, and return one aggregated Snapshot."""
    target = _normalize_url(url)
    observations: list[dict[str, Any]] = []
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(user_agent=USER_AGENT)
                start = await _scrape(context, target, timeout, accept_consent)
                observations.append(start)

                to_visit: list[str] = (
                    discover_links(target, start["html"], max_pages - 1) if max_pages > 1 else []
                )
                for u in extra_pages or []:
                    nu = _normalize_url(u)
                    if nu not in to_visit and nu != target:
                        to_visit.append(nu)
                for u in to_visit:
                    try:
                        observations.append(
                            await _scrape(context, _normalize_url(u), timeout, accept_consent)
                        )
                    except Exception:  # noqa: BLE001 — one bad page shouldn't fail the crawl
                        continue
            finally:
                await browser.close()
    except Exception as exc:  # noqa: BLE001 — collector must never crash the run
        return Snapshot(collector="crawl", target=target, ok=False, error=str(exc))

    valid = [o for o in observations if o.get("html")]
    if not valid:
        return Snapshot(collector="crawl", target=target, ok=False, error="empty render")

    container_ids: set[str] = set(extra_containers or [])
    for o in valid:
        container_ids.update(GTM_SNIPPET.findall(o["html"]))
        for u in o["request_urls"]:
            container_ids.update(GTM_SNIPPET.findall(u))

    import asyncio as _aio

    sorted_ids = sorted(container_ids)
    fetched = await _aio.gather(*(fetch_gtm_container(cid) for cid in sorted_ids))
    containers: dict[str, Any] = dict(zip(sorted_ids, fetched))

    sigs = [
        extract_signals(
            o["html"],
            o["request_urls"],
            containers,
            o["cookies"],
            o["consent"],
            o.get("datalayer_runtime"),
        )
        for o in valid
    ]
    pages = [{"url": o["url"], "http_status": o["http_status"]} for o in valid]

    data = (
        merge_signals(sigs, containers, pages)
        if len(sigs) > 1
        else {**sigs[0], "pages": pages, "pages_scanned": 1}
    )
    data.update({"url": target, "http_status": valid[0]["http_status"], "rendered": True})
    return Snapshot(collector="crawl", target=target, ok=True, data=data)
