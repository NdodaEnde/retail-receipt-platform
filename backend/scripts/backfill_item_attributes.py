"""
Backfill receipt_items with brand/house-brand, pack-size, type-key and GTIN
attributes (migration 006), re-running item_normalizer over every stored line
with the receipt's chain as context.

    python scripts/backfill_item_attributes.py            # dry run — summary + samples
    python scripts/backfill_item_attributes.py --apply    # write (requires migration 006)

No Google/LLM calls — pure rules, safe to re-run any time the registry grows.
"""
import argparse
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from database import get_database  # noqa: E402
from item_normalizer import normalize_item  # noqa: E402
from brand_registry import infer_chain  # noqa: E402

FIELDS = ("canonical_name", "category", "brand", "brand_type", "brand_owner",
          "brand_tier", "pack_size", "pack_unit", "gtin", "type_key")


def retry(fn, attempts=4):
    for i in range(attempts):
        try:
            return fn()
        except Exception:
            if i == attempts - 1:
                raise
            time.sleep(2 ** i)


def main(apply: bool):
    db = get_database()
    client = db.client
    if apply and not db._column_exists("receipt_items", "brand_type"):
        print("❌ migration 006 not applied (receipt_items.brand_type missing) — run it first")
        return

    receipts = retry(lambda: client.table("receipts").select("id,shop_id,shop_name").limit(10000).execute()).data or []
    shops = {s["id"]: s["name"] for s in (retry(lambda: client.table("shops").select("id,name").execute()).data or [])}
    # chain from the canonical branch name first (post Place-ID cleanup), OCR name as fallback
    chain_of = {r["id"]: infer_chain(shops.get(r.get("shop_id")) or r.get("shop_name")) for r in receipts}

    items, start = [], 0
    while True:
        page = retry(lambda: client.table("receipt_items").select("*").range(start, start + 999).execute()).data or []
        items.extend(page)
        if len(page) < 1000:
            break
        start += 1000

    changed, house_counter, size_count, gtin_count = [], Counter(), 0, 0
    cat_before = Counter(i.get("category") or "NULL" for i in items)
    for it in items:
        norm = normalize_item(it.get("name") or "", chain=chain_of.get(it.get("receipt_id")))
        upd = {f: norm[f] for f in FIELDS if norm.get(f) != it.get(f)}
        # numeric compare: '2000.000' (db) vs 2000 (python)
        if "pack_size" in upd and it.get("pack_size") is not None and norm["pack_size"] is not None \
                and abs(float(it["pack_size"]) - float(norm["pack_size"])) < 1e-6:
            del upd["pack_size"]
        if upd:
            changed.append((it["id"], upd))
        if norm["brand_type"] == "house":
            house_counter[f"{norm['brand_owner']} · {norm['brand']}"] += 1
        if norm["pack_size"] is not None:
            size_count += 1
        if norm["gtin"]:
            gtin_count += 1

    total = len(items)
    print(f"{total} item lines scanned → {len(changed)} rows to update ({'APPLY' if apply else 'DRY RUN'})\n")
    print(f"house-brand lines: {sum(house_counter.values())}  ·  with pack size: {size_count} "
          f"({100 * size_count // max(total, 1)}%)  ·  with GTIN: {gtin_count}")
    print("\nHouse brands found:")
    for key, n in house_counter.most_common(20):
        print(f"  {n:>4}  {key}")
    print("\nSample updates:")
    for iid, upd in changed[:12]:
        name = next(i.get("name") for i in items if i["id"] == iid)
        print(f"  · {str(name)[:44]:46} -> " + ", ".join(f"{k}={v!r}" for k, v in upd.items() if v is not None))

    if not apply:
        print("\n(dry run — nothing written)")
        return
    for iid, upd in changed:
        retry(lambda: client.table("receipt_items").update(upd).eq("id", iid).execute())
    print(f"\n✅ {len(changed)} rows updated")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    main(ap.parse_args().apply)
