#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# verify-ontology.sh — self-verification for the KlpIT ontology layer.
#   Layer 1 · Static  : ontology/*.yaml parses
#   Layer 2 · Runtime : validate_ontology.py — consistency + POPIA exposure gate
# Exit 0 = correct. Exit 1 = a gate failed.
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

PY="$(command -v python3)"
[ -z "$PY" ] && { echo "❌ python3 not found"; exit 1; }
if ! "$PY" -c "import yaml" 2>/dev/null; then
  echo "❌ PyYAML missing — run: pip install pyyaml"; exit 1
fi

echo "── Layer 1 · Static (YAML parses) ──"
if "$PY" -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('ontology/*.yaml')]" 2>/tmp/klp_yaml.err; then
  echo "  ✅ all ontology/*.yaml parse"
else
  echo "  ❌ YAML parse error:"; sed 's/^/      /' /tmp/klp_yaml.err; exit 1
fi

echo
echo "── Layer 2 · Runtime (ontology validates + POPIA gate) ──"
if "$PY" scripts/validate_ontology.py; then
  echo
  echo "→ VERIFY OK"
  exit 0
else
  echo
  echo "→ VERIFY FAILED"
  exit 1
fi
