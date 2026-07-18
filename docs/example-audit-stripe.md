# Measurement Audit — https://stripe.com/

_Generated 2026-07-18 20:26 · Adwize Audit (oss edition, public-source scan)_

**Grade B — 75/100**

Status counts: pass=13, warn=7, na=5, fail=1

## Scores by category

| Category | Score |
|---|---|
| Attribution | 100/100 |
| Data Collection | 91/100 |
| Data Quality | 98/100 |
| Privacy | 86/100 |

## Analysis

## Executive summary
Stripe’s public homepage scan shows a generally solid GA4/GTM foundation (no duplicate tags, modern GA4 only) but several implementation gaps drag the grade to a “B”. The most urgent risk is the presence of advertising pixels without any detected consent-management or Google Consent Mode, exposing the business to privacy non-compliance and potential ad-platform enforcement. Operationally, event hygiene (naming, ecommerce coverage, dataLayer usage) and tag placement issues limit data quality, while nine Custom HTML tags and user-provided-data features warrant a security and privacy review. Core page-view tracking fires, but tightening consent, governance, and funnel completeness will unlock reliable insight and mitigate legal risk.

## Findings deep-dive

### 1. No consent management despite advertising tags  
- **What & evidence** – Google Ads conversion ID `AW-848119022` and GA4 (`G-SEKFWD1C9J`) loaded, yet scan shows `consent.accepted = False` and `cmps = []`; no `x-ga-gcs` / `gcd` parameters in network calls.  
- **Why it matters** – Violates EU/UK ePrivacy & GDPR requirements; ad platforms may limit remarketing or suspend accounts. Data collected could be deleted retroactively if challenged.  
- **How to verify** – In live browser DevTools → Network → filter `collect?v=2`, check for `&gcs=` or `gcd=`; in GTM → Admin → Consent Overview (or Tag Assistant Preview → Consent tab) confirm no default/updated states.  
- **How to fix** – Deploy a CMP that sets TCF v2 signals or at minimum implement Google Consent Mode v2 in GTM: add “Consent Initialization” tag, configure `ad_storage`, `analytics_storage`, wire CMP events to `gtag('consent', 'update', …)`.  
- **Effort** – Moderate (needs legal alignment + engineering).

### 2. GTM snippet loads after `<body>`  
- **What & evidence** – Scan flagged “GTM snippet appears after `<body>`”.  
- **Why it matters** – Late container load can miss fast user interactions, degrade remarketing accuracy, and inflate load-time metrics.  
- **How to verify** – View source; GTM `<script src="https://www.googletagmanager.com/gtm.js?id=...">` should be the last tag in `<head>`, not in body.  
- **How to fix** – Move the GTM `<script>` into `<head>` and keep the `<noscript>` iframe immediately after `<body>` (see Google’s install doc).  
- **Effort** – Low (template change).

### 3. `<noscript>` fallback missing  
- **What & evidence** – “GTM `<noscript>` fallback missing” warning.  
- **Why it matters** – Users with JS disabled or corporate script blockers won’t be counted, skewing reach metrics and potentially compliance logs.  
- **How to verify** – View source; confirm absence of `<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=…"></iframe></noscript>` after opening `<body>`.  
- **How to fix** – Add the standard GTM `<noscript>` block immediately inside `<body>`.  
- **Effort** – Low.

### 4. dataLayer not initialised  
- **What & evidence** – “No dataLayer detected” across scanned page.  
- **Why it matters** – Without `window.dataLayer = window.dataLayer || [];` push, any later pushes (e.g., ecommerce events) may fail silently, preventing GTM variables/triggers from reading business data.  
- **How to verify** – Open Console, type `dataLayer`; expect `ReferenceError` or empty variable. GTM Preview → Data Layer tab will be empty.  
- **How to fix** – Declare `window.dataLayer = window.dataLayer || [];` before GTM container snippet; push page context (page type, user status) as needed.  
- **Effort** – Low.

### 5. Inconsistent event naming  
- **What & evidence** – Events “Functional_view” and “Job_Application_View” use PascalCase; other events use snake_case.  
- **Why it matters** – Breaks query patterns and GA4 “recommended events” auto-classification; increases risk of duplicates (“functional_view” vs “Functional_view”).  
- **How to verify** – GA4 Admin → Events list; BigQuery `SELECT DISTINCT event_name`.  
- **How to fix** – Standardise to lowercase snake_case (`functional_view`, `job_application_view`); update GTM tag names & any hard-coded `gtag('event')`.  
- **Effort** – Low (naming convention).

### 6. Incomplete ecommerce funnel  
- **What & evidence** – Only `purchase` event detected; missing `view_item`, `add_to_cart`, `begin_checkout`.  
- **Why it matters** – GA4 “Monetisation” and funnel exploration reports can’t show drop-off, ROAS optimisation signals lost for Ads & Optimize.  
- **How to verify** – Trigger purchase path in GA4 DebugView or GTM Preview; inspect event stream.  
- **How to fix** – Implement GA4 recommended ecommerce events with required `items` array per spec; can be pushed to dataLayer then mapped via GTM.  
- **Effort** – Moderate (requires dev instrumentation across product, cart, checkout).

### 7. User-provided data (enhanced conversions/EUID) enabled without consent proof  
- **What & evidence** – Container flagged `enhanced_conversions = True`, `user_properties = True`; yet no consent mode.  
- **Why it matters** – Email/phone hashes sent to Google demand explicit consent and documented hashing; non-compliant use risks regulatory fines and Google enforcement.  
- **How to verify** – Chrome DevTools → Network → filter for `ec.js` or payloads containing `em=`; decode to verify SHA-256. Check GA4 “User-provided data” diagnostics.  
- **How to fix** – (a) Ensure data is SHA-256 client-side, (b) gate tag firing behind CMP consent signal (`ad_user_data`, `ad_personalization`), or disable enhanced conversions until compliant.  
- **Effort** – Moderate.

### 8. Nine Custom HTML tags in GTM  
- **What & evidence** – Scan lists `custom_html_tags = 9`.  
- **Why it matters** – Custom code bypasses GTM sandbox, can inject PII, slow pages, or create security holes. Hard to audit/QA.  
- **How to verify** – GTM Workspace → Tags → filter Type = Custom HTML; review each tag’s code, triggers, consent settings.  
- **How to fix** – Audit purpose & owner, migrate to template tags where possible, enforce coding standards, add consent checks, and disable unused tags.  
- **Effort** – Moderate to High depending on complexity.

## What to check next
1. Public follow-up scans  
   • Run the crawler again after granting marketing consent in the CMP (or temporarily force `?consent=granted`) to view the full tag landscape.  
   • Scan key transactional pages (pricing > signup, dashboard, checkout) to validate ecommerce events and additional containers.  
   • Provide the GTM container ID in the scanner to ensure hidden/DOM-injected tags are parsed.

2. Deeper manual/account checks to prioritise  
   GA4  
   • Confirm data retention = 14 months and reset-on-new-activity toggle (protects historical analysis).  
   • Review Reporting Identity & Google Signals to ensure choices align with the new consent strategy.  
   • Inspect “Enhanced measurement” and Events list to verify ecommerce events, naming consistency, and mark key events.  
   • Link GA4 to BigQuery and Google Ads if not already – unlock advanced modelling and Ads conversions without duplicate tags.

   GTM  
   • Ensure GA4 Config fires once per page and precedes all event tags to avoid parameter loss.  
   • Implement Consent Mode v2 in GTM (Consent Initialization + Update tags) and test in Tag Assistant Preview.  
   • Validate cross-domain measurement setup if Stripe sends users to sub-domains during checkout.

   Google Ads  
   • Check auto-tagging and audience lists; once consent mode is active, verify conversions aren’t double-counted.

   BigQuery  
   • After linking, set up export-gap monitoring (`bigquery.export_complete_no_gaps`) to guarantee reporting continuity and manage storage cost.

These steps will confirm that the fixes above take effect, close compliance gaps, and improve data reliability for growth and optimisation.

## Findings

### ❌ Advertising tags but no consent management
`crawl.consent_mode_present` · Privacy · **high** · fail

Ad tags are present but no CMP or Google Consent Mode was detected.
- How to check / fix: Look for gtag('consent', ...) / a detected CMP alongside ad tags.

### ⚠️ 9 custom HTML/JS tag(s) in container
`crawl.custom_html_tags` · Data Quality · **medium** · warn

Custom HTML tags warrant a security / performance / PII review.
- How to check / fix: Count __html tags in the public container.

### ⚠️ No dataLayer detected
`crawl.datalayer_present` · Data Collection · **medium** · warn

No dataLayer init or push found; custom event data may not reach GTM.
- How to check / fix: Look for dataLayer init and dataLayer.push() usage.

### ⚠️ Incomplete ecommerce funnel
`crawl.ecommerce_funnel` · Data Collection · **medium** · warn

Present: ['purchase']. Missing: ['view_item', 'add_to_cart', 'begin_checkout'].
- How to check / fix: Check for view_item > add_to_cart > begin_checkout > purchase in the container.

### ⚠️ User-data collection enabled — verify consent
`crawl.enhanced_conversions_review` · Privacy · **medium** · warn

Container enables: enhanced conversions / EUID, user properties. Confirm consent + hashing.
- How to check / fix: Check container flags (enableEuid / enhancedUserId / user properties).

### ⚠️ Inconsistent event naming
`crawl.event_naming_convention` · Data Collection · **medium** · warn

Non snake_case: Functional_view, Job_Application_View. 
- Affected: event=Functional_view, event=Job_Application_View
- How to check / fix: Check container event names for casing variants / mixed conventions.

### ⚠️ GTM snippet appears after <body>
`crawl.gtm_in_head` · Data Collection · **medium** · warn

GTM should load in <head> for earliest execution.
- How to check / fix: Confirm the gtm.js reference appears before <body>.

### ⚠️ GTM <noscript> fallback missing
`crawl.noscript_fallback` · Data Collection · **low** · warn

JS-disabled visitors won't be tracked without the <noscript> iframe.
- How to check / fix: Look for googletagmanager.com/ns.html in a <noscript>.

### ✅ GTM installed: GTM-WK8882T
`crawl.gtm_installed` · Data Collection · **critical** · pass
- How to check / fix: Render the page; look for googletagmanager.com/gtm.js in the DOM.

### ✅ No hardcoded Ads duplication
`crawl.no_hardcoded_ads_duplicate` · Data Quality · **critical** · pass
- How to check / fix: Detect hardcoded AW- gtag while GTM container also has Ads tags.

### ✅ No hardcoded GA4 duplication
`crawl.no_hardcoded_ga4_duplicate` · Data Quality · **critical** · pass
- How to check / fix: Detect hardcoded gtag G- id while GTM container also configures GA4.

### ✅ No PII observed in request query strings
`crawl.no_pii_in_network` · Privacy · **critical** · pass
- How to check / fix: Scan captured request URLs for emails / PII parameter keys.

### ✅ No pushes precede GTM
`crawl.datalayer_push_order` · Data Collection · **high** · pass
- How to check / fix: Confirm no push() appears before the gtm.js reference.

### ✅ No PII-looking event names
`crawl.no_pii_in_events` · Privacy · **high** · pass
- How to check / fix: Scan container event names for PII-looking tokens.

### ✅ Single GTM container
`crawl.single_container` · Data Collection · **high** · pass
- How to check / fix: Count distinct GTM-XXXX ids in the rendered page.

### ✅ All containers parsed successfully
`crawl.container_parsed` · Data Collection · **medium** · pass
- How to check / fix: Check that each fetched gtm.js returned parseable content.

### ✅ No legacy UA properties detected
`crawl.no_legacy_ua` · Data Collection · **low** · pass
- How to check / fix: Detect UA-XXXXXXX-X measurement IDs in gtag or page source.

### ✅ 3 Google recommended events used
`crawl.recommended_event_names` · Data Collection · **low** · pass

Recommended: purchase, search, sign_up
- How to check / fix: Compare container event names against Google's recommended-events list.

### ✅ 1 third-party script domains
`crawl.third_party_script_sprawl` · Data Quality · **low** · pass
- How to check / fix: Count distinct external script domains.

### ✅ 16 GA4 events configured, 0 firing on load
`crawl.event_inventory` · Data Collection · **info** · pass

Configured: Functional_view, Job_Application_View, account_sign_in, activate_account_step, connect_bank_account, cta_button_click, forget_password, form_submission, page_view, product_activation, purchase, scroll, search, sign_up, site_country_change, site_language_change
- How to check / fix: Enumerate vtp_eventName across GA4 event tags in the public container.

### ✅ 2 martech vendor(s) detected
`crawl.vendor_inventory` · Data Collection · **info** · pass

Segment, Google Tag Manager
- How to check / fix: Match vendor signatures across HTML + network beacons.

### ➖ No linker decoration observed
`crawl.cross_domain_linker` · Attribution · **high** · na

No _gl parameter seen; only relevant if cross-domain tracking is intended.
- How to check / fix: Detect linker config in the container and _gl decoration on links.

### ➖ Single container — no cross-container duplication possible
`crawl.no_duplicate_measurement_ids` · Data Quality · **high** · na
- How to check / fix: Check for the same G- ID configured in multiple GTM containers.

### ➖ No GA collect beacons observed
`crawl.consent_signals_sent` · Privacy · **medium** · na
- How to check / fix: Inspect network beacons for gcs/gcd parameters.

### ➖ No cookies observed
`crawl.third_party_cookies` · Privacy · **low** · na
- How to check / fix: Count third-party cookies set after render.

### ➖ No server-side transport detected
`crawl.server_side_transport` · Data Collection · **info** · na
- How to check / fix: Look for transport_url / first-party collect endpoints in beacons.


## Measurement inventory

- **Pages crawled (5):** https://stripe.com/, https://stripe.com/it/newsroom/news/stripe-openai-instant-checkout, https://stripe.com/it/customers/instacart, https://stripe.com/it/contact/sales, https://stripe.com/it/customers/shopify
- **GTM containers:** GTM-WK8882T
- **Measurement IDs:** AW-848119022, G-SEKFWD1C9J
- **Vendors detected:** Segment (analytics), Google Tag Manager (tag_management)
- **Ecommerce:** False · **Enhanced conversions:** True · **Custom HTML tags:** 9
- **Consent:** CMPs=none, accepted=False
- **Cookies:** 0 total, 0 third-party

### GA4 events configured (16)

`Functional_view`, `Job_Application_View`, `account_sign_in`, `activate_account_step`, `connect_bank_account`, `cta_button_click`, `forget_password`, `form_submission`, `page_view`, `product_activation`, `purchase`, `scroll`, `search`, `sign_up`, `site_country_change`, `site_language_change`

## Scoring methodology

The audit starts at **100 points** and deducts penalties for each failing or warning check:

| Severity | FAIL penalty | WARN penalty |
|----------|-------------|-------------|
| Critical | -25 | -12 |
| High | -12 | -6 |
| Medium | -5 | -2 |
| Low | -2 | -1 |
| Info | 0 | 0 |

Grade bands: **A** >= 90, **B** >= 75, **C** >= 60, **D** >= 40, **E** < 40.

Info-severity checks are purely informational (inventory, server-side detection) and do not affect the score.
