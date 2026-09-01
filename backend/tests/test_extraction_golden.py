"""
Golden-set test for receipt field extraction and shop resolution.

    python tests/test_extraction_golden.py                 # offline: verifier rules + adversarial proposals
    python tests/test_extraction_golden.py --live-schema   # + real LandingAI extract() on the stored OCR text
    python tests/test_extraction_golden.py --live-resolve  # + real Google Places/Geocoding resolution

Each receipt in tests/golden_receipts.json is a real (scrubbed) slip with expected
postcode / phone / address / shop name, an adversarial postal-code proposal that
must be rejected, and the place the resolver should land on.
"""
import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from extraction_verifier import verify_extraction, sanitize_shop_name  # noqa: E402

GOLDEN = json.load(open(ROOT / "tests" / "golden_receipts.json"))
FAILS = []


def check(cond, msg, rid):
    if not cond:
        FAILS.append(f"{rid}: {msg}")
    return cond


def accepts(expected, actual):
    if isinstance(expected, list):
        return actual in expected
    return actual == expected


def run_offline():
    print("── offline: verifier on rules alone + adversarial proposals ──")
    for r in GOLDEN:
        rid = r["id"]
        # (a) rules only: proposal is just the stored shop name
        v = verify_extraction(r["raw_text"], {"shop_name": r["proposal_shop_name"]})
        ok = True
        ok &= check(accepts(r["postal"], v["postal_code"]), f"postal expected {r['postal']!r} got {v['postal_code']!r} — {[e for e in v['evidence'] if e.startswith('postal')]}", rid)
        ok &= check(accepts(r["phone"], v["phone_number"]), f"phone expected {r['phone']!r} got {v['phone_number']!r} — {[e for e in v['evidence'] if e.startswith('phone')]}", rid)
        if r["address"] is None:
            pass  # no assertion: absence of address is allowed to be either
        else:
            joined = (v["address"] or "").lower()
            ok &= check(all(t.lower() in joined for t in r["address"]), f"address expected {r['address']} in {v['address']!r}", rid)
        exp_shop = r["shop"]
        got_shop = v["shop_name"]
        if exp_shop is None:
            ok &= check(got_shop is None, f"shop expected None got {got_shop!r}", rid)
        else:
            ok &= check(got_shop is not None and exp_shop.lower().replace("'", "") in got_shop.lower().replace("'", ""), f"shop expected {exp_shop!r} got {got_shop!r}", rid)
        # (b) adversarial: the LLM proposes a wrong postcode — must be rejected
        if r.get("adversarial"):
            va = verify_extraction(r["raw_text"], {"shop_name": r["proposal_shop_name"], "postal_code": r["adversarial"]})
            ok &= check(va["postal_code"] != r["adversarial"], f"adversarial postal {r['adversarial']} ACCEPTED — {[e for e in va['evidence'] if e.startswith('postal')]}", rid)
        # (c) a correct proposal must be accepted (idempotence)
        if isinstance(r["postal"], str):
            vc = verify_extraction(r["raw_text"], {"shop_name": r["proposal_shop_name"], "postal_code": r["postal"]})
            ok &= check(vc["postal_code"] == r["postal"], f"correct proposal {r['postal']} rejected — {[e for e in vc['evidence'] if e.startswith('postal')]}", rid)
        print(("  ✅ " if ok else "  ❌ ") + f"{rid} {r['label']}")


def run_live_schema():
    print("── live: LandingAI extract() on stored OCR text, then verify ──")
    from receipt_processor import get_receipt_processor
    proc = get_receipt_processor()
    import re
    schema = None
    # reuse the schema string from receipt_processor by reading the source (keeps one source of truth)
    src = open(ROOT / "receipt_processor.py").read()
    m = re.search(r'items_schema = json\.dumps\((\{.*?\})\)\n', src, re.S)
    schema = json.dumps(eval(m.group(1)))
    for r in GOLDEN:
        rid = r["id"]
        try:
            resp = proc.client.extract(markdown=r["raw_text"], schema=schema, model="extract-latest")
            data = resp.extraction if resp and hasattr(resp, "extraction") else {}
        except Exception as e:
            print(f"  ⚠️ {rid} extract failed: {e}"); continue
        proposal = {k: data.get(k) for k in ("shop_name", "shop_address", "address_lines", "phone_number", "postal_code", "postal_code_source_line")}
        v = verify_extraction(r["raw_text"], proposal)
        ok = check(accepts(r["postal"], v["postal_code"]), f"[live] postal expected {r['postal']!r} got {v['postal_code']!r} (LLM proposed {proposal.get('postal_code')!r}) — {[e for e in v['evidence'] if e.startswith('postal')]}", rid)
        ok &= check(accepts(r["phone"], v["phone_number"]), f"[live] phone expected {r['phone']!r} got {v['phone_number']!r} (LLM proposed {proposal.get('phone_number')!r})", rid)
        exp_live = r.get("shop_live", r["shop"])
        if exp_live is None:
            ok &= check(v["shop_name"] is None, f"[live] shop expected None got {v['shop_name']!r}", rid)
        else:
            toks = lambda x: {w for w in re.findall(r"[a-z0-9]+", (x or "").lower()) if len(w) >= 3}
            ok &= check(v["shop_name"] is not None and bool(toks(exp_live) & toks(v["shop_name"])), f"[live] shop expected ~{exp_live!r} got {v['shop_name']!r}", rid)
        print(("  ✅ " if ok else "  ❌ ") + f"{rid} LLM: postal={proposal.get('postal_code')!r} phone={proposal.get('phone_number')!r} lines={proposal.get('address_lines')!r:.60} → verified postal={v['postal_code']!r} phone={v['phone_number']!r}")


async def run_live_resolve():
    print("── live: resolve_shop against Google ──")
    from shop_resolver import resolve_shop
    for r in GOLDEN:
        rid = r["id"]
        if r["resolve"] == "skip":
            continue
        v = verify_extraction(r["raw_text"], {"shop_name": r["proposal_shop_name"]})
        cust = r["customer"] or (None, None)
        res = await resolve_shop(v["shop_name"], address=v["address"], address_lines=v["address_lines"],
                                 postal_code=v["postal_code"], phone=v["phone_number"], suburb=v["suburb"],
                                 customer_lat=cust[0], customer_lon=cust[1])
        if r["resolve"] is None:
            print(f"  ·  {rid} (no expectation) → {res.display_name if res else None} [{res.precision if res else 'none'}]")
            continue
        hay = ((res.formatted_address + " " + res.display_name) if res else "").lower()
        ok = check(res is not None and any(t.lower() in hay for t in r["resolve"]),
                   f"[resolve] expected one of {r['resolve']} got {res.formatted_address if res else None} — {res.evidence if res else 'unresolved'}", rid)
        print(("  ✅ " if ok else "  ❌ ") + f"{rid} {res.display_name if res else None} [{res.precision if res else 'none'}] via {res.source if res else '-'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live-schema", action="store_true")
    ap.add_argument("--live-resolve", action="store_true")
    a = ap.parse_args()
    run_offline()
    if a.live_schema:
        run_live_schema()
    if a.live_resolve:
        asyncio.run(run_live_resolve())
    print()
    for f in FAILS:
        print("  ❌", f)
    print(f"RESULT: {'ALL PASS' if not FAILS else str(len(FAILS)) + ' FAILED'} over {len(GOLDEN)} receipts")
    sys.exit(1 if FAILS else 0)
