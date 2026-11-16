---
name: contratos
description: Como criar ou alterar uma mensagem SQS (JSON Schema + exemplo) ou um endpoint HTTP (OpenAPI) no fiapx-docs, com versionamento e validação. Use antes de mudar qualquer integração entre serviços.
---

# Contratos

## Mensagem SQS

1. Schema em `contracts/<mensagem-em-kebab>.v<versão>.schema.json` (draft 2020-12), com
   `additionalProperties: false` (produtor estrito). O envelope comum está em `contracts/envelope.schema.json`.
2. Exemplo válido em `contracts/examples/<mensagem>.v<versão>.json` (variações: `--sufixo.json`).
3. Atualize a tabela "Filas, mensagens, produtores e consumidores" em `contracts/README.md` e o
   `validate-contracts.sh`, se ele lista os pares schema/exemplo.
4. Rode `./scripts/validate-contracts.sh`. Para regras condicionais (`if/then`), teste também exemplos
   inválidos à mão: o schema precisa rejeitá-los.
5. Mudança incompatível = nova `version` (arquivo `.v2`), mantendo a `.v1` durante a transição: consumidor
   aceita as duas → produtor passa a emitir a nova → remove a antiga quando a fila esvaziar.

## Endpoint HTTP

1. Altere `api/openapi.yaml` (paths, schemas, exemplos e respostas de erro, inclusive 401/403/422).
2. Rode o Spectral (comando na skill `validar-docs`).
3. Se a rota passa pelo authorizer ou muda o fluxo, atualize `03-arquitetura/sequencias.md` e o README do
   repositório dono.

Depois do merge aqui, os repositórios produtor e consumidor ajustam o código e os contract tests.
