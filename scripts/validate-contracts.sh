#!/usr/bin/env bash
# Compila os JSON Schemas de contracts/ (modo estrito) e valida cada exemplo contra o seu schema.
# Convenção: contracts/examples/<nome>[--<variante>].json é validado contra contracts/<nome>.schema.json.
set -euo pipefail
cd "$(dirname "$0")/../contracts"
AJV="npx -y -p ajv-cli@5 -p ajv-formats@3 ajv"
fail=0
$AJV compile --spec=draft2020 --strict=true -c ajv-formats -s envelope.schema.json >/dev/null || fail=1
for ex in examples/*.json; do
  name=$(basename "$ex" .json); name=${name%%--*}   # exemplos extras: <nome>--<variante>.json
  schema="$name.schema.json"
  if [ ! -f "$schema" ]; then echo "ERRO  sem schema para $ex"; fail=1; continue; fi
  refs=(); [ "$schema" != envelope.schema.json ] && refs=(-r envelope.schema.json)
  if $AJV validate --spec=draft2020 --strict=true -c ajv-formats -s "$schema" "${refs[@]}" -d "$ex" >/dev/null 2>&1; then
    echo "ok    $ex"
  else
    echo "ERRO  $ex"; $AJV validate --spec=draft2020 --strict=true -c ajv-formats -s "$schema" "${refs[@]}" -d "$ex" || true; fail=1
  fi
done
for s in *.schema.json; do
  n=${s%.schema.json}; [ "$n" = envelope ] && continue
  [ -f "examples/$n.json" ] || { echo "ERRO  $s sem exemplo"; fail=1; }
done
exit $fail
