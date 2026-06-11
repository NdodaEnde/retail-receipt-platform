# KlpIT Ontology Layer

An intelligence + governance layer over the receipt platform, adapted from the
`claude-framework` ontology spine (built for Tshwane EIMS). The ontology is
**declared, not coded**: it lives in `ontology/*.yaml` and a validator proves it
is internally consistent and that the POPIA exposure rule holds.

## Run it
```bash
./scripts/verify-ontology.sh        # parses YAML + validates + prints the POPIA report
```
Exit 0 = valid. The validator is the machine-checkable form of "is this safe to expose?".

## The pillars
| File | Pillar | Purpose |
|------|--------|---------|
| `meta.yaml` | Meta | UID domains, source systems, **O/P/F/X sensitivity classes**, roles, the external-exposure rule |
| `objects.yaml` | Objects | `customer`, `receipt`, `receipt_item`, `shop`, `draw`, `product` — every property tagged with a sensitivity class |
| `functions.yaml` | Functions | The intelligence layer — computed insights bound to objects/aggregates, each with `output_class`, `exposure`, `min_users`, `phase` |
| `links.yaml` | Links | Typed relationships (the object graph) |
| `actions.yaml` | Actions | The only write path — role-gated, mapped to `backend/server.py` endpoints |

## Why it earns its place
1. **POPIA gate** — a function with `exposure: external` must emit `output_class: X`.
   Personal (`P`) and Financial (`F`) data physically cannot reach a B2B/public
   surface without the build failing. The report lists exactly what is exposable
   vs locked.
2. **Roadmap as code** — `functions.yaml` mirrors the `CLAUDE.md` intelligence
   tiers via `min_users` + `phase`. Most functions already exist as SQL views;
   this declares them with sensitivity and a release phase.
3. **Item-normalization bottleneck** has a home — object `product` + link
   `normalizes_to` + function `itemNormalization`.

## How to extend
- New insight → add to `functions.yaml` with `reads`, `output_class`, `exposure`.
- New table/column → add to `objects.yaml` with a sensitivity class (the
  validator fails if any property is untagged).
- Re-run `./scripts/verify-ontology.sh`. If you mark something external that
  reads P/F without aggregating to X, the gate stops you.

`product` is **planned** (resolves the item-normalization bottleneck); it is
declared ahead of implementation so downstream functions can bind to it.
