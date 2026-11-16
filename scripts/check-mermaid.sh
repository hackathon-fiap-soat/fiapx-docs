#!/usr/bin/env bash
# Renderiza todos os blocos ```mermaid de todos os .md e falha se algum tiver erro de sintaxe.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=.mermaid-check
rm -rf "$OUT" && mkdir -p "$OUT"
MMDC="npx -y @mermaid-js/mermaid-cli@11.4.2"
fail=0; total=0
while IFS= read -r f; do
  grep -q '```mermaid' "$f" || continue
  total=$((total+1))
  name=$(echo "$f" | tr '/' '_')
  if $MMDC -q -i "$f" -o "$OUT/$name" ${PUPPETEER_CFG:+-p "$PUPPETEER_CFG"} >"$OUT/$name.log" 2>&1; then
    echo "ok    $f"
  else
    echo "ERRO  $f"; sed -n '1,15p' "$OUT/$name.log"; fail=1
  fi
done < <(find . -name '*.md' -not -path './node_modules/*' -not -path "./$OUT/*" | sort)
echo "$total arquivo(s) com Mermaid verificados."
exit $fail
