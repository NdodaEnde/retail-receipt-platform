"""
Share of wallet by suburb — pure aggregation, no I/O (ontology: suburbWalletShare).

Input: receipts carrying upload_suburb (the customer's suburb, a home proxy) and
shops for names/chains. Output: per suburb, how its residents' observed spend is
split across branches, plus a chain roll-up.

Honesty rules baked in:
  * unit of split is the *branch* (most shops on the platform are independents;
    a chain-only split would lump two thirds of them as "Other")
  * a suburb with fewer than K_FLOOR distinct customers is `thin`: one person's
    spending with a thin disguise. The admin surface shows it dimmed; anything
    public must drop it (see suppress_thin)
  * what is measured is share of *submitted* spend among platform users, not the
    suburb's true wallet — label it that way until volume is real
"""
from collections import defaultdict
from typing import Dict, Iterable, List, Optional

K_FLOOR = 5
INDEPENDENT = "Independent"


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def compute_wallet_share(receipts: Iterable[dict], shops: Iterable[dict],
                         k_floor: int = K_FLOOR) -> Dict:
    """
    receipts: dicts with upload_suburb, upload_locality, upload_latitude/longitude,
              shop_id, shop_name, amount, customer_phone, status
    shops:    dicts with id, name, chain
    Returns {"suburbs": [...], "unassigned": n, "k_floor": k}
    """
    shop_by_id = {s["id"]: s for s in shops if s.get("id")}
    buckets: Dict[str, dict] = {}
    unassigned = 0

    for r in receipts:
        if r.get("status") == "rejected":
            continue
        suburb = (r.get("upload_suburb") or "").strip()
        if not suburb:
            if r.get("upload_latitude") is not None:
                unassigned += 1
            continue
        amount = _f(r.get("amount"))
        b = buckets.get(suburb)
        if b is None:
            b = buckets[suburb] = {
                "suburb": suburb, "locality": r.get("upload_locality"),
                "lat_sum": 0.0, "lon_sum": 0.0, "points": 0,
                "customers": set(), "receipts": 0, "spend": 0.0,
                "shops": defaultdict(lambda: {"receipts": 0, "spend": 0.0, "customers": set()}),
            }
        if r.get("upload_latitude") is not None and r.get("upload_longitude") is not None:
            b["lat_sum"] += _f(r["upload_latitude"]); b["lon_sum"] += _f(r["upload_longitude"]); b["points"] += 1
        phone = (r.get("customer_phone") or "").lstrip("+")
        b["customers"].add(phone)
        b["receipts"] += 1
        b["spend"] += amount
        key = r.get("shop_id") or f"name:{(r.get('shop_name') or 'Unknown shop').strip().lower()}"
        sb = b["shops"][key]
        sb["receipts"] += 1; sb["spend"] += amount; sb["customers"].add(phone)
        sb.setdefault("shop_id", r.get("shop_id"))
        sb.setdefault("name", r.get("shop_name") or "Unknown shop")

    out: List[dict] = []
    for b in buckets.values():
        total = b["spend"] or 0.0
        split = []
        for key, sb in b["shops"].items():
            shop = shop_by_id.get(sb.get("shop_id")) or {}
            split.append({
                "shop_id": sb.get("shop_id"),
                "name": shop.get("name") or sb["name"],
                "chain": shop.get("chain") or INDEPENDENT,
                "receipts": sb["receipts"],
                "customers": len(sb["customers"]),
                "spend": round(sb["spend"], 2),
                "share": round(sb["spend"] / total, 4) if total else 0.0,
            })
        split.sort(key=lambda x: (-x["spend"], x["name"]))

        chains: Dict[str, float] = defaultdict(float)
        for s in split:
            chains[s["chain"]] += s["spend"]
        chain_rows = sorted(
            [{"chain": c, "spend": round(v, 2), "share": round(v / total, 4) if total else 0.0} for c, v in chains.items()],
            key=lambda x: -x["spend"],
        )
        n_customers = len(b["customers"])
        out.append({
            "suburb": b["suburb"], "locality": b["locality"],
            "latitude": round(b["lat_sum"] / b["points"], 6) if b["points"] else None,
            "longitude": round(b["lon_sum"] / b["points"], 6) if b["points"] else None,
            "customers": n_customers, "receipts": b["receipts"], "spend": round(total, 2),
            "thin": n_customers < k_floor,
            "leader": split[0] if split else None,
            "split": split, "chains": chain_rows,
        })
    out.sort(key=lambda x: -x["spend"])
    return {"suburbs": out, "unassigned": unassigned, "k_floor": k_floor}


def suppress_thin(result: Dict) -> Dict:
    """The X-class form: drop suburbs under the k-floor and every per-shop customer count."""
    kept = []
    for s in result["suburbs"]:
        if s["thin"]:
            continue
        s = dict(s)
        s["split"] = [{k: v for k, v in row.items() if k != "customers"} for row in s["split"]]
        s["leader"] = s["split"][0] if s["split"] else None
        s.pop("latitude", None); s.pop("longitude", None)
        kept.append(s)
    return {**result, "suburbs": kept, "suppressed": len(result["suburbs"]) - len(kept)}


def round_coord(lat: Optional[float], lon: Optional[float], places: int = 3):
    """Cache key for reverse geocoding: 3 dp ≈ 110 m, well inside a suburb."""
    if lat is None or lon is None:
        return None
    return (round(float(lat), places), round(float(lon), places))
