"""
Backfill: re-resolve shop locations that were pinned to the geographic centre of
South Africa (Google's "country" match), never resolved, or whose distance-based
fraud flag is not 'valid' (possible wrong-branch geocode); recompute distance and
fraud assessment, and release false-positive fraud holds.

    python scripts/backfill_geocode.py                    # dry run — prints what would change
    python scripts/backfill_geocode.py --apply            # write changes
    python scripts/backfill_geocode.py --fill-precision   # after migration 003: set
                                  # receipts.geocode_precision from the shop record (no Google calls)

Safe by construction:
  * never touches receipts with status 'won' or 'rejected'
  * only moves status review -> processed when the new assessment is not 'flagged'
  * shops are upgraded only when the new precision beats what is stored
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from geocoding import is_sa_centroid, precision_rank  # noqa: E402
import server  # noqa: E402  (loads db, geocoder; scheduler only starts under uvicorn)


def fmt(v):
    return "—" if v is None else (f"{v:.4f}" if isinstance(v, float) else str(v))


async def main(apply: bool):
    db = server.db
    client = db.client
    has_precision_col = db._column_exists("receipts", "geocode_precision")

    rows = client.table("receipts").select(
        "id,created_at,shop_id,shop_name,shop_address,shop_latitude,shop_longitude,"
        "upload_latitude,upload_longitude,distance_km,fraud_flag,fraud_score,status"
    ).order("created_at", desc=True).limit(2000).execute().data or []

    targets = [
        r for r in rows
        if r.get("shop_name")
        and r.get("status") not in ("won", "rejected")
        and (
            is_sa_centroid(r.get("shop_latitude"), r.get("shop_longitude"))
            or r.get("shop_latitude") is None
            or r.get("fraud_flag") in ("review", "suspicious", "flagged")
        )
    ]
    print(f"{len(rows)} receipts scanned → {len(targets)} to re-resolve "
          f"({'APPLY' if apply else 'DRY RUN'}; geocode_precision column "
          f"{'present' if has_precision_col else 'MISSING — run migration 003'})\n")

    changed = released = 0
    shop_updates = {}  # shop_id -> best (rank, update dict)

    for r in targets:
        name = server.sanitize_shop_name(r["shop_name"])
        if not name:
            print(f"· {r['id'][:8]} {r['shop_name']!r:32} → non-shop name, skipping")
            continue
        lat, lon, display, _, precision = await server.geocode_shop_from_receipt(
            name, r.get("shop_address"), None,
            customer_lat=r.get("upload_latitude"), customer_lon=r.get("upload_longitude"),
        )
        distance = None
        if lat is not None and r.get("upload_latitude") is not None:
            distance = server.calculate_distance_km(lat, lon, r["upload_latitude"], r["upload_longitude"])
        assessment = server.assess_fraud_risk(
            distance, 0,
            customer_located=r.get("upload_latitude") is not None,
            shop_precision=precision,
        )
        new_status = r["status"]
        if r["status"] == "review" and assessment["fraud_flag"] != "flagged":
            new_status = "processed"

        moved_km = None
        if lat is not None and r.get("shop_latitude") is not None:
            moved_km = server.calculate_distance_km(lat, lon, r["shop_latitude"], r["shop_longitude"])
        unchanged = (
            moved_km is not None and moved_km < 2.0  # same mall/precinct, not worth a write
            and assessment["fraud_flag"] == r["fraud_flag"] and new_status == r["status"]
        )
        if unchanged:
            continue
        print(f"· {r['id'][:8]} {name!r:32} {fmt(r.get('distance_km')):>8} km → {fmt(distance):>8} km  "
              f"[{precision:7}] {r['fraud_flag']:10}→{assessment['fraud_flag']:10} "
              f"{r['status']}→{new_status}   {display}")
        update = {
            "shop_latitude": lat, "shop_longitude": lon,
            "distance_km": round(distance, 2) if distance is not None else None,
            "fraud_flag": assessment["fraud_flag"],
            "fraud_score": assessment["fraud_score"],
            "fraud_reason": assessment["fraud_reason"],
            "status": new_status,
        }
        if has_precision_col:
            update["geocode_precision"] = precision
        changed += 1
        released += int(new_status != r["status"])

        if r.get("shop_id") and lat is not None:
            rank = precision_rank(precision)
            if rank > shop_updates.get(r["shop_id"], (-1, None))[0]:
                shop_updates[r["shop_id"]] = (rank, {
                    "latitude": lat, "longitude": lon,
                    "geocode_confidence": precision,
                    "geocoded_at": datetime.now(timezone.utc).isoformat(),
                })

        if apply:
            client.table("receipts").update(update).eq("id", r["id"]).execute()

    # Shops still at the centroid with no receipt to drive them get cleared to NULL
    centroid_shops = client.table("shops").select("id,name,latitude,longitude,geocode_confidence") \
        .eq("latitude", -30.559482).execute().data or []
    for shop in centroid_shops:
        if shop["id"] not in shop_updates:
            shop_updates[shop["id"]] = (0, {"latitude": None, "longitude": None,
                                            "geocode_confidence": "none"})

    print(f"\n{len(shop_updates)} shop rows to update:")
    for sid, (rank, upd) in shop_updates.items():
        print(f"· shop {sid[:8]} → ({fmt(upd['latitude'])}, {fmt(upd['longitude'])}) [{upd['geocode_confidence']}]")
        if apply:
            client.table("shops").update(upd).eq("id", sid).execute()

    print(f"\nReceipts updated: {changed}   fraud holds released: {released}   "
          f"shops updated: {len(shop_updates)}   {'(written)' if apply else '(dry run — nothing written)'}")


async def fill_precision(apply: bool):
    """Populate receipts.geocode_precision where NULL, from the linked shop's
    geocode_confidence (or 'none' when the receipt has no shop coordinates)."""
    db = server.db
    client = db.client
    if not db._column_exists("receipts", "geocode_precision"):
        print("receipts.geocode_precision missing — run migrations/003_geocode_precision.sql first")
        return
    receipts = client.table("receipts").select("id,shop_id,shop_latitude").is_("geocode_precision", "null") \
        .limit(5000).execute().data or []
    shops = {s["id"]: s for s in (client.table("shops").select("id,geocode_confidence").execute().data or [])}
    counts = {}
    for r in receipts:
        if r.get("shop_latitude") is None:
            value = "none"
        else:
            value = (shops.get(r.get("shop_id")) or {}).get("geocode_confidence")
            if value in (None, "high", "medium", "low"):
                continue  # legacy coordinates of unknown precision — leave NULL
        counts[value] = counts.get(value, 0) + 1
        if apply:
            client.table("receipts").update({"geocode_precision": value}).eq("id", r["id"]).execute()
    print(f"{len(receipts)} receipts without precision → set {counts} {'(written)' if apply else '(dry run)'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    ap.add_argument("--fill-precision", action="store_true",
                    help="only fill receipts.geocode_precision from shop records")
    args = ap.parse_args()
    asyncio.run(fill_precision(args.apply) if args.fill_precision else main(args.apply))
