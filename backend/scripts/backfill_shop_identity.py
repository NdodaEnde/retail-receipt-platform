"""
Backfill shop identity: resolve every receipt's shop through the full pipeline
(verify_extraction on the stored OCR text -> resolve_shop), key shops by Google
Place ID, merge duplicates, repoint receipts, recompute shop stats.

    python scripts/backfill_shop_identity.py            # dry run: prints the plan
    python scripts/backfill_shop_identity.py --apply    # requires migration 004

Google calls are cached per (name, address, phone, ~customer) so repeated slips
from the same shop cost one lookup.
"""
import argparse
import asyncio
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from extraction_verifier import verify_extraction, sanitize_shop_name  # noqa: E402
from shop_resolver import resolve_shop  # noqa: E402
from geocoding import precision_rank, is_sa_centroid  # noqa: E402
import server  # noqa: E402


async def main(apply: bool):
    db = server.db
    client = db.client
    ready = db._column_exists("shops", "place_id") and db._column_exists("shop_aliases", "alias")
    if apply and not ready:
        print("❌ migration 004 not applied (shops.place_id / shop_aliases missing) — run it first")
        return

    receipts = client.table("receipts").select(
        "id,shop_id,shop_name,shop_address,raw_text,upload_latitude,upload_longitude,"
        "shop_latitude,shop_longitude,amount,status,fraud_flag,distance_km"
    ).order("created_at").limit(5000).execute().data or []
    shops = {s["id"]: s for s in (client.table("shops").select("*").execute().data or [])}
    print(f"{len(receipts)} receipts, {len(shops)} shops")

    # 1. resolve each receipt (cached)
    cache, resolved, unresolved = {}, {}, []
    for r in receipts:
        proposal = {"shop_name": r.get("shop_name"), "shop_address": r.get("shop_address")}
        v = verify_extraction(r.get("raw_text") or "", proposal) if r.get("raw_text") else {
            "shop_name": sanitize_shop_name(r.get("shop_name")), "address": r.get("shop_address"),
            "address_lines": None, "postal_code": None, "phone_number": None, "suburb": None}
        if not v["shop_name"]:
            unresolved.append((r, "no shop name")); continue
        cl = (round(r["upload_latitude"], 2), round(r["upload_longitude"], 2)) if r.get("upload_latitude") is not None else (None, None)
        key = (v["shop_name"].lower(), (v["address"] or "").lower(), v["phone_number"], cl)
        if key not in cache:
            cache[key] = await resolve_shop(v["shop_name"], address=v["address"], address_lines=v["address_lines"],
                                            postal_code=v["postal_code"], phone=v["phone_number"], suburb=v["suburb"],
                                            customer_lat=cl[0], customer_lon=cl[1])
        res = cache[key]
        if res and res.place_id:
            resolved[r["id"]] = (r, v, res)
        else:
            unresolved.append((r, f"resolved without place id [{res.precision}]" if res else "unresolved"))
    print(f"→ {len(resolved)} receipts resolved to a Place ID ({len(cache)} Google lookups), {len(unresolved)} left as-is\n")

    # 2. group by place_id and choose the surviving shop row per branch
    groups = defaultdict(list)
    for rid, (r, v, res) in resolved.items():
        groups[res.place_id].append((r, v, res))

    plan_shop_updates, plan_new_shops, plan_receipts, merged_away = {}, {}, {}, set()
    by_place = {s["place_id"]: s for s in shops.values() if s.get("place_id")}
    for pid, rows in groups.items():
        res = max((x[2] for x in rows), key=lambda x: precision_rank(x.precision))
        phone = next((x[1]["phone_number"] for x in rows if x[1]["phone_number"]), None)
        current_ids = [x[0]["shop_id"] for x in rows if x[0].get("shop_id") in shops]
        target = by_place.get(pid)
        if not target and current_ids:
            # the legacy shop most of these receipts already point to, if it has no place_id
            # and is at the same place; else create a fresh branch row
            best = max(set(current_ids), key=current_ids.count)
            cand = shops[best]
            if not cand.get("place_id") and server._same_place(cand, res.latitude, res.longitude):
                target = cand
        if target:
            upd = {"place_id": pid, "name": res.display_name, "latitude": res.latitude, "longitude": res.longitude,
                   "geocode_confidence": res.precision, "geocoded_at": datetime.now(timezone.utc).isoformat()}
            if phone: upd["phone"] = phone
            if not target.get("address"): upd["address"] = res.formatted_address
            plan_shop_updates[target["id"]] = (target, upd)
            target_id = target["id"]
        else:
            target_id = f"new:{pid}"
            plan_new_shops[target_id] = {"name": res.display_name, "address": res.formatted_address, "place_id": pid,
                                         "phone": phone, "latitude": res.latitude, "longitude": res.longitude,
                                         "geocode_confidence": res.precision}
        aliases = sorted({x[1]["shop_name"] for x in rows} | {x[0]["shop_name"] for x in rows if x[0].get("shop_name")})
        for r, v, rr in rows:
            plan_receipts[r["id"]] = (r, target_id, rr, aliases)
        for sid in set(current_ids):
            if sid != target_id and sid in shops and not shops[sid].get("place_id"):
                merged_away.add(sid)

    # a legacy shop is only deleted if *all* its receipts move elsewhere
    receipts_by_shop = defaultdict(list)
    for r in receipts:
        if r.get("shop_id"): receipts_by_shop[r["shop_id"]].append(r["id"])
    merged_away = {sid for sid in merged_away if all(rid in plan_receipts and plan_receipts[rid][1] != sid for rid in receipts_by_shop[sid])}

    # 3. report
    print(f"Branches: {len(groups)}  → claim/upgrade {len(plan_shop_updates)} existing shops, create {len(plan_new_shops)}, "
          f"delete {len(merged_away)} emptied duplicates; repoint {len(plan_receipts)} receipts\n")
    for sid, (shop, upd) in plan_shop_updates.items():
        print(f"· claim   {shop['name']!r:36} → {upd['name']!r} [{upd['geocode_confidence']}] {upd['place_id'][:20]}…")
    for tid, doc in plan_new_shops.items():
        print(f"· create  {doc['name']!r:36} [{doc['geocode_confidence']}] {doc['place_id'][:20]}…")
    for sid in merged_away:
        print(f"· delete  {shops[sid]['name']!r:36} (all {len(receipts_by_shop[sid])} receipts moved)")
    print("\nUnresolved (unchanged):")
    for r, why in unresolved:
        print(f"· {r['id'][:8]} {str(r.get('shop_name'))[:30]!r:32} {why}")

    if not apply:
        print("\n(dry run — nothing written)"); return

    # 4. apply
    new_ids = {}
    for tid, doc in plan_new_shops.items():
        row = await db.shops_insert_one(dict(doc))
        new_ids[tid] = row["id"]
    for sid, (shop, upd) in plan_shop_updates.items():
        client.table("shops").update(upd).eq("id", sid).execute()
    touched = set()
    for rid, (r, target_id, res, aliases) in plan_receipts.items():
        sid = new_ids.get(target_id, target_id)
        touched.add(sid)
        upd = {"shop_id": sid}
        if res.latitude is not None and (r.get("shop_latitude") is None or is_sa_centroid(r.get("shop_latitude"), r.get("shop_longitude"))
                                         or server.calculate_distance_km(res.latitude, res.longitude, r["shop_latitude"], r["shop_longitude"]) > 0.5):
            upd.update({"shop_latitude": res.latitude, "shop_longitude": res.longitude})
            if r.get("upload_latitude") is not None:
                d = server.calculate_distance_km(res.latitude, res.longitude, r["upload_latitude"], r["upload_longitude"])
                a = server.assess_fraud_risk(d, r.get("amount") or 0, customer_located=True, shop_precision=res.precision)
                upd.update({"distance_km": round(d, 2), "fraud_flag": a["fraud_flag"], "fraud_score": a["fraud_score"], "fraud_reason": a["fraud_reason"]})
                if r["status"] == "review" and a["fraud_flag"] != "flagged":
                    upd["status"] = "processed"
        if db._column_exists("receipts", "geocode_precision"):
            upd["geocode_precision"] = res.precision
        client.table("receipts").update(upd).eq("id", rid).execute()
        for alias in aliases:
            await db.shop_alias_add(sid, alias)
    for sid in merged_away:
        client.table("shops").delete().eq("id", sid).execute()
    # 5. recompute stats for touched shops
    for sid in touched:
        rows = client.table("receipts").select("amount,status").eq("shop_id", sid).neq("status", "rejected").execute().data or []
        client.table("shops").update({"receipt_count": len(rows), "total_sales": round(sum(float(x["amount"] or 0) for x in rows), 2)}).eq("id", sid).execute()
    print(f"\n✅ written: {len(plan_new_shops)} shops created, {len(plan_shop_updates)} claimed, {len(merged_away)} deleted, "
          f"{len(plan_receipts)} receipts repointed, {len(touched)} shop stats recomputed")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    asyncio.run(main(ap.parse_args().apply))
