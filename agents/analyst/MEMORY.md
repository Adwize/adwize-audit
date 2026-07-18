# Analyst agent — memory

Curated heuristics for interpreting public-scan findings. Committed and
reviewable; the schema-maintainer/analyst learnings accrue here over time.

- **Double-firing is the top offender.** GA4 or Ads loaded both hardcoded
  (gtag) and via GTM double-counts sessions, conversions, and revenue — always
  rank `crawl.no_hardcoded_*_duplicate` failures first; frame impact in
  inflated-conversions / wasted-ad-spend terms.
- **Consent gating hides the real setup.** If a CMP is present and few tags/
  events are visible, the analytics container likely loads post-consent — note
  that the scan reflects a pre/partial-consent state and recommend a re-scan with
  consent accepted (or supplying the container id).
- **Empty container ≠ clean.** A container with 0 events on the homepage often
  means events live in a second container or fire only on deeper pages (PDP,
  cart). Flag as "coverage unknown from homepage", not "no tracking".
- **Enhanced conversions / user-provided data** must be tied to a consent basis
  and be hashed — always call it out for a privacy/legal check, never assume ok.
- **Custom HTML tags** are the usual home of PII leaks, performance drags, and
  unreviewed third-party code — recommend a security review when count > 0.
