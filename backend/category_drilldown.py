"""
Category drill-down — pure aggregation, no I/O (ontology: categoryDrilldown).

Answers the brand-client question behind "Beverages: R2 900": which *kind* of
beverage (sub-category), which brand, which product and pack size — and at
every level, where (chain, customer suburb) and how many distinct shoppers.

    category -> sub-category -> brand -> product (type_key + pack size)

Honesty rules baked in:
  * every node carries `customers` and `thin` (< K_FLOOR distinct shoppers):
    one or two people's habits with a thin disguise. Admin shows them dimmed;
    nothing external without the k-floor
  * coverage is reported, not hidden: share of lines with an identified brand /
    pack size. Unidentified brands are a bucket of their own, never dropped
  * a line whose total disagrees with qty x unit price is an OCR misread of one
    of the two (seen: "Coke Zero 3 x R40 = R295"). We count the smaller and
    report how many lines conflicted
  * spend is *submitted* spend among platform users, not market size
"""
from collections import Counter, defaultdict
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from item_normalizer import subcategorize

K_FLOOR = 5
INDEPENDENT = "Independent"
NO_BRAND = "Brand not identified"
NO_SUBURB = "Suburb unknown"


def _f(v) -> Optional[float]:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def line_spend(item: dict) -> Tuple[float, bool]:
    """(spend, conflicted). Conflicted = total and qty x unit disagree by > R1 and > 2%."""
    total, qty, unit = _f(item.get("total_price")), _f(item.get("quantity")), _f(item.get("unit_price"))
    if qty and unit:
        implied = qty * unit
        if total is None:
            return implied, False
        if abs(total - implied) > max(1.0, 0.02 * max(total, implied)):
            return min(total, implied), True
    return (total or 0.0), False


def pack_label(size, unit) -> Optional[str]:
    size = _f(size)
    if not size or not unit:
        return None
    if unit == "ml" and size >= 1000:
        size, unit = size / 1000, "L"
    elif unit == "g" and size >= 1000:
        size, unit = size / 1000, "kg"
    elif unit == "each":
        return f"{size:g} pack" if size > 1 else None
    return f"{size:g} {unit}"


def _share_rows(counter_spend: Dict[str, float], counter_people: Dict[str, set], total: float,
                key_name: str, k_floor: int, with_thin: bool) -> List[dict]:
    rows = []
    for k, v in counter_spend.items():
        row = {key_name: k, "spend": round(v, 2), "share": round(v / total, 4) if total else 0.0,
               "customers": len(counter_people[k])}
        if with_thin:
            row["thin"] = row["customers"] < k_floor
        rows.append(row)
    rows.sort(key=lambda r: (-r["spend"], r[key_name]))
    return rows


def _node(lines: List[dict], name: str, parent_spend: Optional[float], k_floor: int) -> dict:
    spend = sum(l["spend"] for l in lines)
    customers = {l["customer"] for l in lines if l["customer"]}
    chain_spend, chain_people = defaultdict(float), defaultdict(set)
    sub_spend, sub_people = defaultdict(float), defaultdict(set)
    for l in lines:
        chain_spend[l["chain"]] += l["spend"]; chain_people[l["chain"]].add(l["customer"])
        sub_spend[l["suburb"]] += l["spend"]; sub_people[l["suburb"]].add(l["customer"])
    n = len(lines)
    return {
        "name": name,
        "spend": round(spend, 2),
        "share": round(spend / parent_spend, 4) if parent_spend else 1.0,
        "lines": n,
        "units": round(sum(l["qty"] for l in lines), 2),
        "receipts": len({l["receipt_id"] for l in lines}),
        "customers": len(customers),
        "thin": len(customers) < k_floor,
        "coverage": {
            "brand": round(sum(1 for l in lines if l["brand"]) / n, 3) if n else 0.0,
            "pack": round(sum(1 for l in lines if l["pack"]) / n, 3) if n else 0.0,
            "price_conflicts": sum(1 for l in lines if l["conflict"]),
        },
        "chains": _share_rows(chain_spend, chain_people, spend, "chain", k_floor, False),
        "suburbs": _share_rows(sub_spend, sub_people, spend, "suburb", k_floor, True),
    }


def _products(lines: List[dict]) -> List[dict]:
    groups: Dict[tuple, List[dict]] = defaultdict(list)
    for l in lines:
        groups[(l["type_key"], l["pack"])].append(l)
    out = []
    for (_, pack), ls in groups.items():
        spend = sum(l["spend"] for l in ls)
        units = sum(l["qty"] for l in ls)
        label = Counter(l["label"] for l in ls).most_common(1)[0][0]
        out.append({
            "name": label, "pack": pack, "spend": round(spend, 2), "lines": len(ls),
            "units": round(units, 2), "receipts": len({l["receipt_id"] for l in ls}),
            "customers": len({l["customer"] for l in ls if l["customer"]}),
            "avg_unit_price": round(spend / units, 2) if units else None,
            "conflicts": sum(1 for l in ls if l["conflict"]),
        })
    out.sort(key=lambda p: (-p["spend"], p["name"]))
    return out


def _children(lines: List[dict], key: Callable[[dict], str], parent_spend: float, k_floor: int) -> List[dict]:
    groups: Dict[str, List[dict]] = defaultdict(list)
    for l in lines:
        groups[key(l)].append(l)
    return sorted(({**_node(ls, k, parent_spend, k_floor), "_lines": ls} for k, ls in groups.items()),
                  key=lambda n: (-n["spend"], n["name"]))


def compute_category_drilldown(category: str, items: Iterable[dict], receipts: Iterable[dict],
                               shops: Iterable[dict], k_floor: int = K_FLOOR,
                               chain_of: Optional[Callable[[Optional[str]], Optional[str]]] = None) -> Dict:
    """
    items:    receipt_items rows (receipt_id, name, quantity, unit_price, total_price,
              canonical_name, category, brand, brand_type, pack_size, pack_unit, type_key)
    receipts: id, status, customer_phone, shop_id, shop_name, upload_suburb (optional)
    shops:    id, name, chain (optional)
    chain_of: fallback name -> chain resolver when shops.chain is missing
    Returns the category node with nested `subcategories[].brands[].products[]`.
    """
    rec_by_id = {r["id"]: r for r in receipts if r.get("id")}
    shop_by_id = {s["id"]: s for s in shops if s.get("id")}

    lines = []
    for it in items:
        if (it.get("category") or "Other") != category:
            continue
        rec = rec_by_id.get(it.get("receipt_id"))
        if not rec or rec.get("status") == "rejected":
            continue
        shop = shop_by_id.get(rec.get("shop_id")) or {}
        chain = shop.get("chain")
        if chain is None and chain_of:
            chain = chain_of(shop.get("name") or rec.get("shop_name"))
        spend, conflict = line_spend(it)
        name = it.get("name") or it.get("canonical_name") or ""
        lines.append({
            "receipt_id": rec["id"],
            "customer": (rec.get("customer_phone") or "").lstrip("+"),
            "chain": chain or INDEPENDENT,
            "suburb": (rec.get("upload_suburb") or "").strip() or NO_SUBURB,
            "sub": subcategorize(category, name),
            "brand": it.get("brand"),
            "brand_type": it.get("brand_type"),
            "type_key": it.get("type_key") or (it.get("canonical_name") or name).lower(),
            "label": it.get("canonical_name") or name.strip().title(),
            "pack": pack_label(it.get("pack_size"), it.get("pack_unit")),
            "qty": _f(it.get("quantity")) or 1.0,
            "spend": spend,
            "conflict": conflict,
        })

    root = _node(lines, category, None, k_floor)
    root["k_floor"] = k_floor
    subs = _children(lines, lambda l: l["sub"], root["spend"], k_floor)
    for sub in subs:
        brands = _children(sub.pop("_lines"), lambda l: l["brand"] or NO_BRAND, sub["spend"], k_floor)
        for b in brands:
            bl = b.pop("_lines")
            types = Counter(l["brand_type"] for l in bl if l["brand_type"])
            b["brand_type"] = types.most_common(1)[0][0] if types else None
            b["products"] = _products(bl)
        sub["brands"] = brands
    root["subcategories"] = subs
    return root
