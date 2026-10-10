"""
Backfill for migration 007 (share of wallet by suburb):
  * receipts.upload_suburb / upload_locality from the upload coordinates
    (Google reverse geocoding on points rounded to ~110 m, one call per distinct point)
  * shops.chain from brand_registry.infer_chain

    python scripts/backfill_suburbs.py           # dry run: Google calls needed + chain preview
    python scripts/backfill_suburbs.py --apply   # write, then print the wallet-share preview

Requires migration 007 (backend/migrations/007_wallet_share.sql) to have been run.
"""
import argparse
import asyncio
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from supabase import create_client  # noqa: E402
from brand_registry import infer_chain  # noqa: E402
from geocoding import get_geocoding_service  # noqa: E402
from wallet_share import compute_wallet_share, round_coord  # noqa: E402


def rows(client, table, cols):
    out, start = [], 0
    while True:
        batch = client.table(table).select(cols).range(start, start + 999).execute().data or []
        out += batch
        if len(batch) < 1000:
            return out
        start += 1000


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write suburbs and chains")
    args = ap.parse_args()
    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

    try:
        client.table("receipts").select("upload_suburb").limit(1).execute()
        client.table("shops").select("chain").limit(1).execute()
    except Exception:
        sys.exit("Migration 007 has not been run — paste backend/migrations/007_wallet_share.sql "
                 "into the Supabase SQL editor first.")

    # ── shops.chain
    shops = rows(client, "shops", "id,name,chain")
    chain_updates = [(s, infer_chain(s["name"])) for s in shops if not s.get("chain")]
    chain_updates = [(s, c) for s, c in chain_updates if c]
    print(f"shops: {len(shops)} | chain to set on {len(chain_updates)}: "
          + ", ".join(f"{c} ×{n}" for c, n in Counter(c for _, c in chain_updates).most_common()))

    # ── receipts.upload_suburb
    receipts = rows(client, "receipts", "id,upload_latitude,upload_longitude,upload_suburb")
    todo = [r for r in receipts if r.get("upload_latitude") is not None and not r.get("upload_suburb")]
    points = {round_coord(r["upload_latitude"], r["upload_longitude"]) for r in todo}
    print(f"receipts: {len(receipts)} | need a suburb: {len(todo)} | distinct points (= Google calls): {len(points)}"
          f" — Geocoding API, first 10 000/month free")

    if not args.apply:
        print("\nDry run — nothing written. Re-run with --apply.")
        return

    for s, c in chain_updates:
        client.table("shops").update({"chain": c}).eq("id", s["id"]).execute()

    geo = get_geocoding_service()
    areas = {}
    for p in points:
        areas[p] = await geo.reverse_geocode_area(*p)
    found = 0
    for r in todo:
        area = areas.get(round_coord(r["upload_latitude"], r["upload_longitude"]))
        if area:
            client.table("receipts").update(
                {"upload_suburb": area["suburb"], "upload_locality": area["locality"]}).eq("id", r["id"]).execute()
            found += 1
    print(f"\nchains set: {len(chain_updates)} | suburbs set: {found} of {len(todo)}")

    # ── preview
    result = compute_wallet_share(
        rows(client, "receipts", "upload_suburb,upload_locality,upload_latitude,upload_longitude,"
                                 "shop_id,shop_name,amount,customer_phone,status"),
        rows(client, "shops", "id,name,chain"))
    print(f"\nWallet share preview — {len(result['suburbs'])} suburbs, "
          f"{result['unassigned']} receipts with a location but no suburb:")
    for s in result["suburbs"][:10]:
        lead = s["leader"] or {"name": "-", "share": 0}
        print(f"  {s['suburb']:<24} {s['customers']:>2} customers  R{s['spend']:>10,.2f}"
              f"  leader: {lead['name']} ({lead['share']:.0%}){'  [thin]' if s['thin'] else ''}")


if __name__ == "__main__":
    asyncio.run(main())
