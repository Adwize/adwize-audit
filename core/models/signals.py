"""Typed shape for crawl snapshot data.

Checks and report code access `snapshot.data` via string keys on a plain dict.
This TypedDict documents the expected shape so contributors know what keys are
available and what types they hold.
"""

from __future__ import annotations

from typing import Any, TypedDict


class TagIds(TypedDict):
    ga4: list[str]
    ads: list[str]
    ua: list[str]
    gtm: list[str]


class DataLayer(TypedDict):
    init: bool
    push: bool
    push_before_gtm: bool


class ConsentSignals(TypedDict):
    consent_mode: bool
    cmps: list[str]
    signals_seen: bool
    accepted: bool
    accepted_cmp: str | None


class Noscript(TypedDict):
    present: bool
    ids: list[str]


class CrossDomain(TypedDict):
    linker_seen: bool


class Network(TypedDict):
    collect_hits: int
    gcs_seen: bool
    server_side: bool
    server_side_urls: list[str]
    firing_events: list[str]
    pii_hosts: list[str]


class Cookies(TypedDict):
    total: int
    third_party: int


class Vendor(TypedDict):
    name: str
    category: str
    pattern: str


class ContainerSummary(TypedDict):
    events: list[str]
    measurement_ids: list[str]
    ecommerce: bool
    user_properties: bool
    enhanced_conversions: bool
    custom_html_count: int
    has_floodlight: bool
    has_ads: bool
    has_ga4: bool
    vendors: list[str]


class PageInfo(TypedDict):
    url: str
    http_status: int


class CrawlSignals(TypedDict, total=False):
    """The shape of `Snapshot.data` produced by the crawl collector.

    Marked `total=False` because single-page crawls omit some keys
    (e.g. `pages`, `pages_scanned`) that only appear in multi-page merges.
    """

    url: str
    http_status: int
    rendered: bool
    tag_ids: TagIds
    gtm_in_head: bool
    datalayer: DataLayer
    consent: ConsentSignals
    noscript: Noscript
    cross_domain: CrossDomain
    third_party_domains: list[str]
    network: Network
    cookies: Cookies
    vendors: list[Vendor]
    containers: dict[str, dict[str, Any]]
    container_summary: ContainerSummary
    pages: list[PageInfo]
    pages_scanned: int
