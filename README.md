# fiapx-docs

Documentação do **Hackathon FIAP X — Processador de Vídeos** (PÓS TECH SOAT, Fase 5): visão geral,
Domain Storytelling, C4, sequências, SAGA, modelo de dados, ADRs, RFCs, fluxo de deploy, observabilidade,
contratos de mensagens (JSON Schema), OpenAPI e documento de entrega.

A documentação vem antes do código: os outros repositórios implementam o que está descrito aqui.

## Índice

### 1. Contexto

- [Visão geral](01-contexto/visao-geral.md): problema, objetivos, requisitos e diagnóstico do projeto base
- [Linguagem ubíqua](01-contexto/linguagem-ubiqua.md): glossário e mapa de contextos

### 2. Domain Storytelling

- [Notação e Egon.io](02-domain-storytelling/README.md)
- [DS-01 Cadastro e login](02-domain-storytelling/ds-01-cadastro-e-login.md)
- [DS-02 Envio de vídeo](02-domain-storytelling/ds-02-envio-de-video.md)
- [DS-03 Processamento com sucesso](02-domain-storytelling/ds-03-processamento-com-sucesso.md)
- [DS-04 Falha e notificação](02-domain-storytelling/ds-04-falha-e-notificacao.md)
- [DS-05 Consulta de status e download](02-domain-storytelling/ds-05-consulta-status-e-download.md)

### 3. Arquitetura

- [C4 — contexto](03-arquitetura/c4-contexto.md)
- [C4 — containers](03-arquitetura/c4-containers.md)
- [C4 — componentes do video-api](03-arquitetura/c4-componentes-video-api.md)
- [Diagramas de sequência](03-arquitetura/sequencias.md)
- [SAGA orquestrada](03-arquitetura/saga.md)
- [Modelo de dados e scripts](03-arquitetura/modelo-de-dados.md)
- [Segurança](03-arquitetura/seguranca.md)
- [Escalabilidade e resiliência](03-arquitetura/escalabilidade-e-resiliencia.md)

### 4. Decisões

- [ADRs](04-adrs/README.md) (16 decisões)
- [RFCs](05-rfcs/README.md) (10 comparações de alternativas)

### 5. Deploy e operação

- [Fluxo de deploy](06-deploy/fluxo-de-deploy.md): pipelines, ordem entre repositórios e rollback
- [Ambientes](06-deploy/ambientes.md): local e produção, custos e destroy
- [Observabilidade](07-observabilidade/observabilidade.md) e
  [dashboard do New Relic](07-observabilidade/newrelic-dashboard.json)

### 6. Contratos

- [Mensagens (JSON Schema)](contracts/README.md)
- [API HTTP (OpenAPI 3.1)](api/openapi.yaml)

### 7. Entrega

- [Documento de entrega](entrega/entrega-fase5.md) (rascunho, exportado para PDF na Etapa 10)
- [Roteiro do vídeo](entrega/roteiro-video.md)

## Repositórios do projeto

| Repositório | Responsabilidade |
|---|---|
| [`fiapx-docs`](https://github.com/hackathon-fiap-soat/fiapx-docs) | Esta documentação |
| [`fiapx-infra`](https://github.com/hackathon-fiap-soat/fiapx-infra) | VPC, EKS (add-ons), Aurora MySQL, S3, SQS/DLQ, SES, ECR, API Gateway + VPC Link + ALB interno, Secrets, OIDC do GitHub, outputs no SSM e ambiente local (docker-compose + LocalStack) |
| [`fiapx-auth`](https://github.com/hackathon-fiap-soat/fiapx-auth) | Lambdas de register, login e authorizer (JWT RS256) e rotas `/api/auth/*` no API Gateway |
| [`fiapx-video-api`](https://github.com/hackathon-fiap-soat/fiapx-video-api) | Gestão de vídeos, POST pré-assinado no S3, listagem de status, download e orquestração da SAGA (outbox e consumidores idempotentes) |
| [`fiapx-video-processor`](https://github.com/hackathon-fiap-soat/fiapx-video-processor) | Consome `ProcessVideo`/`CleanupArtifacts`, extrai 1 frame por segundo com ffmpeg, gera o zip no S3 e responde à SAGA. Escalado por KEDA |
| [`fiapx-notification`](https://github.com/hackathon-fiap-soat/fiapx-notification) | Fila SQS → Lambda que envia e-mail via SES, registra cada envio no DynamoDB (chave = e-mail) e responde à SAGA |
| [`fiapx-web`](https://github.com/hackathon-fiap-soat/fiapx-web) | Cadastro, login, upload de vários vídeos, lista de status e download do zip. Servido por S3 + CloudFront |

## Stack

Markdown, Mermaid, JSON Schema (draft 2020-12) e OpenAPI 3.1.

## Como validar localmente

Pré-requisito: Node.js 20 ou superior. Os comandos rodam com `npx`, sem instalar nada no projeto.

```bash
# Markdown
npx markdownlint-cli2@0.18.1 "**/*.md"

# Contratos: compila os schemas e valida cada exemplo
./scripts/validate-contracts.sh

# OpenAPI
npx @stoplight/spectral-cli@6.15.0 lint api/openapi.yaml --ruleset api/.spectral.yaml

# Diagramas Mermaid: renderiza todos os blocos e falha se algum tiver erro de sintaxe
./scripts/check-mermaid.sh
```

O workflow [`docs.yml`](.github/workflows/docs.yml) roda as mesmas validações em todo pull request.

Para ver os diagramas, abra os arquivos no GitHub (renderiza Mermaid nativamente) ou no VS Code com a
extensão *Markdown Preview Mermaid Support*.

## Contribuição

- A branch `main` é protegida: toda mudança entra por Pull Request (a aprovação é opcional; qualquer
  integrante, inclusive o autor, pode fazer o merge).
- O `README.md` deve estar sempre atualizado: toda mudança que afete propósito, stack, como rodar/testar,
  variáveis de ambiente ou links atualiza este arquivo no mesmo PR.
- Nova decisão de arquitetura, ou decisão que contrarie uma existente, vira um ADR novo em `04-adrs/`.
- Mudança em contrato de mensagem segue a regra de versionamento de [`contracts/README.md`](contracts/README.md).
- Nunca commitar segredos (`.env`, chaves, tokens). Use `.env.example` com valores fictícios.

## Licença

[MIT](LICENSE)
