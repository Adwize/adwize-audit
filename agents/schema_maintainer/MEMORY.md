# Schema-maintainer agent — memory

Owns the audit knowledge schemas (`core/schemas/*.yaml`). Its skill: find things
the current schemas don't yet explain (unknown GTM tag functions, undetected
vendor hosts) from real scans, classify them, and write updated schemas to the
override dir (`$ADWIZE_SCHEMA_DIR`) — which the loader prefers over the committed
fallback. These heuristics are curated and committed.

- **Tag `function` codes**: built-in templates are `__` + short code (`__gaawe`
  GA4 event, `__googtag` Google tag, `__awct` Ads conversion, `__sp` Ads
  remarketing, `__fls`/`__flc` Floodlight, `__html` custom HTML). Gallery/custom
  templates are `__cvt_<hash>` — vendor is usually identifiable only from the
  template's network calls, not the code, so default them to `custom`.
- **Only tag-array functions matter** for vendor mapping. Container macros/
  triggers (`__v`, `__jsm`, `__e`, `__cl`, `__u`, `__k`, `__zone`, `__remm`,
  `__smm`) are internal GTM plumbing — do not add them as vendors.
- **Promote conservatively**: write a new mapping only after seeing a function on
  multiple sites, and prefer `vendor: custom, purpose: "needs review"` over a
  wrong guess. The committed YAML is the fallback for everyone.
- **Vendor signatures** should key off a stable host or global (e.g.
  `connect.facebook.net`, `bat.bing.com`, `ttq.`) — not brittle inline markup.
