#!/usr/bin/env python3
"""
Validate the KlpIT ontology against its own design principles.

The ontology is *declared, not coded* — it lives in ontology/*.yaml and THIS
script checks that the declaration is internally consistent and obeys the POPIA
exposure rule (a function that is exposed externally must emit only X-class data).

It also prints a SENSITIVITY / EXPOSURE REPORT — the practical payoff: exactly
which computed insights are safe to expose to a B2B / public consumer, which are
locked because they touch Personal/Financial data, and which depend on
anonymization being correct.

Exit 0 = ontology valid. Exit 1 = at least one violation.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("FATAL: PyYAML not installed (pip install pyyaml)", file=sys.stderr)
    sys.exit(3)

ROOT = Path(__file__).resolve().parent.parent
ONT = ROOT / "ontology"
SCHEMA = ROOT / "backend" / "schema.sql"


def schema_views() -> set[str]:
    """Parse CREATE VIEW names from backend/schema.sql (so implemented_by:view:X is real)."""
    if not SCHEMA.exists():
        return set()
    text = SCHEMA.read_text()
    return set(re.findall(r"create\s+(?:or\s+replace\s+)?view\s+([a-zA-Z_][a-zA-Z0-9_]*)",
                          text, re.IGNORECASE))

# Non-action sources a link may legitimately be derived from.
NON_ACTION_DERIVATIONS = {"model_pipeline", "schedule", "dispatch"}


def load(name: str) -> dict:
    with open(ONT / name) as f:
        return yaml.safe_load(f)


def parse_targets(to: str) -> list[str]:
    return [t.strip() for t in str(to).split("|")]


def main() -> int:
    meta = load("meta.yaml")
    objects = load("objects.yaml")["objects"]
    links = load("links.yaml")["links"]
    actions = load("actions.yaml")["actions"]
    functions = load("functions.yaml")["functions"]

    obj_names = set(objects)
    act_names = set(actions)
    fn_names = set(functions)
    domains = set(meta["uid_domains"])
    systems = set(meta["source_systems"]) | {"function", "model", "model_registry"}
    classes = set(meta["sensitivity_classes"])
    roles = set(meta["roles"])
    aggregates = set(meta.get("aggregates", []))
    allowed_writes = set(meta["allowed_action_write_targets"])
    ext_ok_classes = set(meta["external_exposure_allowed_output_classes"])
    views = schema_views()

    # property sensitivity lookup: {object: {prop: class}}
    prop_class: dict[str, dict[str, str]] = {}
    for name, o in objects.items():
        prop_class[name] = {p["name"]: p.get("sensitivity") for p in o["properties"]}

    errors: list[str] = []

    def check(ok, msg):
        if not ok:
            errors.append(msg)

    # ── Identity spine ───────────────────────────────────────────────────────
    for name, o in objects.items():
        prefix = o["uid_prefix"]
        # domain = everything up to the object-letter suffix; match longest declared domain
        matched = any(prefix == d or prefix.startswith(d + "-") for d in domains)
        check(matched, f"[identity] {name}: uid_prefix '{prefix}' not under a declared UID domain")
        check(o["pk_format"].startswith(prefix),
              f"[identity] {name}: pk_format '{o['pk_format']}' does not start with '{prefix}'")

    # ── Every property carries a sensitivity class; SoRs declared ────────────
    for name, o in objects.items():
        for p in o["properties"]:
            check(p.get("sensitivity") in classes,
                  f"[sensitivity] {name}.{p['name']}: class '{p.get('sensitivity')}' not declared")
        for s in o["systems_of_record"]:
            check(s in systems, f"[declared] {name}: system_of_record '{s}' not a source system")

    # ── Links resolve ────────────────────────────────────────────────────────
    for lname, l in links.items():
        check(l["from"] in obj_names, f"[declared] link {lname}: 'from' object '{l['from']}' unknown")
        for t in parse_targets(l["to"]):
            check(t in obj_names or t == "any", f"[declared] link {lname}: 'to' object '{t}' unknown")
        d = l.get("derived_from")
        check(d in act_names or d in systems or d in NON_ACTION_DERIVATIONS,
              f"[declared] link {lname}: derived_from '{d}' not a known action/system/pipeline")

    # ── Actions: roles, write targets, object refs ───────────────────────────
    for aname, a in actions.items():
        for r in a.get("roles", []):
            check(r in roles, f"[declared] action {aname}: role '{r}' not in role matrix")
        for w in a.get("writes_to", []):
            check(w in allowed_writes,
                  f"[write-path] action {aname}: writes_to '{w}' NOT an allowed write target")
        for slot in ("creates", "updates", "reads"):
            for obj in a.get(slot, []):
                check(obj in obj_names, f"[declared] action {aname}: {slot} unknown object '{obj}'")
        for inv in a.get("auto_invokes", []):
            check(inv in act_names, f"[declared] action {aname}: auto_invokes unknown '{inv}'")
        for f in a.get("invokes_function", []):
            check(f in fn_names, f"[declared] action {aname}: invokes_function unknown '{f}'")

    # ── Functions: bindings, reads resolve, POPIA exposure gate ──────────────
    for fname, fn in functions.items():
        for b in fn["bound_to"]:
            check(b in obj_names or b in aggregates,
                  f"[declared] function {fname}: bound_to '{b}' neither object nor aggregate")
        for r in fn.get("reads", []):
            if "." not in r:
                errors.append(f"[declared] function {fname}: read '{r}' not in object.property form")
                continue
            obj, prop = r.split(".", 1)
            check(obj in obj_names and prop in prop_class.get(obj, {}),
                  f"[declared] function {fname}: reads unknown property '{r}'")
        check(fn.get("output_class") in classes,
              f"[sensitivity] function {fname}: output_class '{fn.get('output_class')}' not declared")
        for inv in fn.get("invokes", []):
            check(inv in act_names, f"[declared] function {fname}: invokes unknown action '{inv}'")
        if fn.get("emits"):
            check(fn["emits"] in obj_names, f"[declared] function {fname}: emits unknown object '{fn['emits']}'")
        # THE GATE: external exposure requires an allowed output class
        if fn.get("exposure") == "external":
            check(fn.get("output_class") in ext_ok_classes,
                  f"[POPIA] function {fname}: exposure:external but output_class "
                  f"'{fn.get('output_class')}' is not externally allowed {sorted(ext_ok_classes)}")
        # Build status: implemented_by must be app | planned | view:<existing view>
        impl = fn.get("implemented_by", "planned")
        if impl.startswith("view:"):
            vname = impl.split(":", 1)[1]
            check(vname in views,
                  f"[build] function {fname}: implemented_by view '{vname}' not found in backend/schema.sql")
        else:
            check(impl in ("app", "planned"),
                  f"[build] function {fname}: implemented_by '{impl}' must be app | planned | view:<name>")

    # ── Report ───────────────────────────────────────────────────────────────
    def sens_of(read: str) -> str | None:
        if "." not in read:
            return None
        obj, prop = read.split(".", 1)
        return prop_class.get(obj, {}).get(prop)

    print("── Sensitivity / Exposure report ──")
    # property class distribution
    dist: dict[str, int] = {}
    for o in objects.values():
        for p in o["properties"]:
            dist[p.get("sensitivity")] = dist.get(p.get("sensitivity"), 0) + 1
    print("  Properties by class: " + ", ".join(f"{k}={dist.get(k,0)}" for k in ("O", "P", "F", "X")))

    external, locked, aggregation_dependent = [], [], []
    for fname, fn in functions.items():
        reads = fn.get("reads", [])
        touches_pf = {sens_of(r) for r in reads} & {"P", "F"}
        if fn.get("exposure") == "external":
            external.append(fname)
            if touches_pf:
                aggregation_dependent.append((fname, sorted(touches_pf)))
        elif touches_pf:
            locked.append((fname, sorted(touches_pf)))

    # build status: live (SQL view), live (app code), planned
    live_view, live_app, planned = [], [], []
    for fname, fn in functions.items():
        impl = fn.get("implemented_by", "planned")
        if impl.startswith("view:"):
            live_view.append(f"{fname}->{impl.split(':',1)[1]}")
        elif impl == "app":
            live_app.append(fname)
        else:
            planned.append(f"{fname} (phase {fn.get('phase')}, {fn.get('min_users')}+ users)")
    print(f"\n  Build status: {len(live_view)} SQL views · {len(live_app)} app-code · {len(planned)} planned")
    print(f"     live (view): {', '.join(live_view) or '(none)'}")
    print(f"     live (app):  {', '.join(live_app) or '(none)'}")
    print("     planned:")
    for p in planned:
        print(f"       • {p}")

    print(f"\n  ✅ Externally exposable (B2B/public safe): {', '.join(external) or '(none)'}")
    print("\n  🔒 Internal-only because they read Personal/Financial data:")
    for fname, cls in locked:
        print(f"       {fname}  (reads {','.join(cls)})")
    if aggregation_dependent:
        print("\n  ⚠️  External BUT read P/F inputs — exposure is only safe if aggregation/anonymization is correct:")
        for fname, cls in aggregation_dependent:
            print(f"       {fname}  (reads {','.join(cls)} -> must emit anonymized X)")

    # ── Verdict ──────────────────────────────────────────────────────────────
    print()
    if errors:
        print(f"❌ {len(errors)} violation(s):")
        for e in errors:
            print(f"   {e}")
        return 1
    n = len(objects) + len(links) + len(actions) + len(functions)
    print(f"✅ Ontology valid — {len(objects)} objects, {len(links)} links, "
          f"{len(actions)} actions, {len(functions)} functions ({n} declared types) consistent; POPIA gate holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
