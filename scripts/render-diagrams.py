#!/usr/bin/env python3
"""Extrai todos os blocos ```mermaid dos .md e gera PNG e SVG em diagramas/, com um índice.

Uso: python3 scripts/render-diagrams.py   (precisa de Node.js; usa npx @mermaid-js/mermaid-cli)
Variável opcional PUPPETEER_CFG: caminho de um JSON de configuração do Puppeteer (ex.: --no-sandbox no CI).
"""
import os, re, subprocess, sys, shutil, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "diagramas")
MMDC = ["npx", "-y", "@mermaid-js/mermaid-cli@11.4.2"]

os.chdir(ROOT)
src_dir = os.path.join(OUT, "_src")
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(src_dir)

entries = []
for md in sorted(glob.glob("**/*.md", recursive=True)):
    if md.startswith(("diagramas/", "node_modules/", ".mermaid-check/")):
        continue
    text = open(md, encoding="utf-8").read()
    heading, n = None, 0
    title_doc = re.search(r"^# (.+)$", text, re.M)
    title_doc = title_doc.group(1).strip() if title_doc else md
    in_block, buf, in_other = False, [], False
    for line in text.splitlines():
        if not in_block and line.startswith("```"):
            if line.strip() == "```mermaid":
                in_block, buf = True, []
            else:
                in_other = not in_other
            continue
        if in_block:
            if line.strip() == "```":
                in_block = False
                n += 1
                base = md[:-3].replace("/", "__") + f"-{n:02d}"
                open(os.path.join(src_dir, base + ".mmd"), "w", encoding="utf-8").write("\n".join(buf) + "\n")
                entries.append((md, title_doc, heading or title_doc, base))
            else:
                buf.append(line)
            continue
        if not in_other:
            m = re.match(r"^#{2,4} (.+)$", line)
            if m:
                heading = m.group(1).strip()

cfg = os.environ.get("PUPPETEER_CFG")
fail = 0
for md, _, _, base in entries:
    src = os.path.join(src_dir, base + ".mmd")
    for ext, extra in (("svg", []), ("png", ["-s", "2", "-b", "white"])):
        cmd = MMDC + ["-q", "-i", src, "-o", os.path.join(OUT, f"{base}.{ext}")] + extra + (["-p", cfg] if cfg else [])
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            fail = 1
            print(f"ERRO  {base}.{ext}\n{r.stderr[-600:]}")
    print(f"ok    {base}")

shutil.rmtree(src_dir)
lines = [
    "# Imagens dos diagramas",
    "",
    "Imagens geradas automaticamente a partir dos blocos Mermaid da documentação, para usar no documento",
    "de entrega, em slides e no vídeo. **Não edite estes arquivos à mão**: altere o diagrama no Markdown de",
    "origem e rode `python3 scripts/render-diagrams.py`.",
    "",
    f"Total: {len(entries)} diagramas, cada um em PNG (escala 2x, fundo branco) e SVG.",
    "",
]
current = None
for md, title_doc, heading, base in entries:
    if md != current:
        lines += ["", f"## {title_doc}", "", f"Origem: [`{md}`](../{md})", "", "| Diagrama | PNG | SVG |", "|---|---|---|"]
        current = md
    lines.append(f"| {heading} | [{base}.png]({base}.png) | [{base}.svg]({base}.svg) |")
open(os.path.join(OUT, "README.md"), "w", encoding="utf-8").write("\n".join(lines).replace("\n\n\n", "\n\n") + "\n")
print(f"{len(entries)} diagramas gerados em diagramas/")
sys.exit(fail)
