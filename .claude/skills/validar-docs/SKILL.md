---
name: validar-docs
description: Roda localmente as mesmas validações do CI do fiapx-docs (markdownlint, contratos, OpenAPI, Mermaid, imagens dos diagramas e links). Use antes de commitar qualquer mudança neste repositório.
---

# Validar a documentação

Rode na raiz do `fiapx-docs` (precisa de Node.js e Python 3):

```bash
npx -y markdownlint-cli2@0.18.1 "**/*.md"
./scripts/validate-contracts.sh
npx -y @stoplight/spectral-cli@6.15.0 lint api/openapi.yaml --ruleset api/.spectral.yaml --fail-severity=error
./scripts/check-mermaid.sh
python3 scripts/render-diagrams.py --check
```

Todos precisam terminar sem erro. Também confira os links relativos dos arquivos alterados (o CI não
checa links): todo `](caminho.md)` precisa existir a partir da pasta do arquivo.

Armadilhas conhecidas:

- `;` dentro de mensagem de `sequenceDiagram` quebra o Mermaid: use `,`.
- markdownlint: títulos não podem pular nível (MD001); MD013 (tamanho de linha) está desligado.
- ajv em modo estrito: todo `if/then` precisa de `type` e das propriedades declaradas.
