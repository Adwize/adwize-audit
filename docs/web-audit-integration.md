# Web Audit Integration Design

How to expose adwize-audit as a free web-based audit tool on the Adwize platform
(getadwize.com/audit) for lead generation.

## Goal

Provide a tagstack.io-style experience: paste a URL, get a graded audit report,
capture email for full results. Funnel visitors from "free scan" into the full
Adwize event-monitoring platform.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  getadwize.com/audit                                     │
│                                                          │
│  [URL input] ──POST──▶ /api/v1/audit/scan               │
│                              │                           │
│                              ▼                           │
│                     Background worker                    │
│                     (Playwright + adwize-audit-core)     │
│                              │                           │
│                              ▼                           │
│                     AuditResult stored in DB             │
│                              │                           │
│                              ▼                           │
│  [Result page] ◀──── Grade + top findings (public)      │
│  [Email gate]  ◀──── Full report / PDF (gated)          │
│                              │                           │
│                              ▼                           │
│                     Lead → CRM / nurture sequence        │
└─────────────────────────────────────────────────────────┘
```

## Integration steps

### 1. Import adwize-audit-core as a dependency

In the `adwize/` commercial repo:

```toml
# pyproject.toml
dependencies = [
    "adwize-audit-core @ git+https://github.com/Adwize/adwize-audit.git",
    ...
]
```

Or install from a published PyPI package once available.

### 2. API endpoint

```python
# api/routers/audit.py

@router.post("/api/v1/audit/scan")
async def start_audit(request: AuditRequest, background_tasks: BackgroundTasks):
    """Queue a public-source audit scan. Returns a scan ID for polling."""
    scan_id = uuid4()
    background_tasks.add_task(run_audit_scan, scan_id, request.url)
    return {"scan_id": scan_id, "status": "queued"}

@router.get("/api/v1/audit/{scan_id}")
async def get_audit_result(scan_id: UUID):
    """Poll for scan completion. Returns grade + findings when ready."""
    ...
```

### 3. Background processing

Playwright scans take 15-30 seconds. Options:

- **FastAPI BackgroundTasks** — simplest, works for low volume
- **Task queue (ARQ / Celery)** — for scale, with worker pool and retry
- **Dedicated worker process** — like adwize-oss pattern (cron-based)

Start with BackgroundTasks, move to ARQ if needed.

### 4. Result page (public portion)

Show without authentication:
- Overall grade (A–E) with score
- Category breakdown (Data Collection, Data Quality, Privacy, Attribution)
- Top 3 findings with severity badges
- Vendor stack detected

### 5. Email gate (gated portion)

Require email to access:
- Full finding details with recommendations
- Downloadable PDF/Markdown report
- "What to check next" section (the 69 authenticated checkpoints)
- LLM analyst brief (premium differentiator)

### 6. Rate limiting

- 3 scans per IP per day without account
- 10 scans per day with free account
- Unlimited for paid plans
- Queue depth cap to prevent abuse (max 20 concurrent scans)

### 7. Data model

```sql
CREATE TABLE web_audit_scans (
    id UUID PRIMARY KEY,
    url TEXT NOT NULL,
    status TEXT DEFAULT 'queued',  -- queued | running | completed | failed
    grade TEXT,
    score INTEGER,
    findings JSONB,
    lead_email TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);
```

### 8. Lead capture flow

1. Scan completes → show grade + teaser
2. "Get full report" button → email input modal
3. On submit: store email, unlock full results, trigger nurture sequence
4. Nurture email #1 (immediate): full report attached
5. Nurture email #2 (day 3): "Here's what Adwize monitors in real-time"
6. Nurture email #3 (day 7): "Book a 15-min walkthrough"

## Differentiation vs. tagstack.io

| Aspect | Tagstack | Adwize Audit |
|--------|----------|-------------|
| Focus | Container structure (tags/triggers/variables) | Measurement quality (consent, PII, ecommerce, events) |
| Scoring | Container health grade | 100-point deterministic score with severity weights |
| Actionability | Lists what's there | Tells you what's wrong and how to fix it |
| Trust | Closed-source | Open-source core (verifiable methodology) |
| Upsell | Paid container features | Full event monitoring platform |

## Timeline

- **Week 1**: Ship adwize-audit OSS
- **Week 2-3**: `/api/v1/audit/scan` endpoint + minimal result page
- **Week 4**: Email gate, PDF export, first nurture email
- **Ongoing**: More checks, community PRs, conversion optimization
