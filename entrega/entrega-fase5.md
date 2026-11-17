# Hackathon FIAP X — Entrega da Fase 5

> **Rascunho.** Os campos marcados com "a preencher" são completados na Etapa 10, antes de exportar
> este documento para PDF.

## Participantes

| Nome | RM |
|---|---|
| Diego Fenille | rm372271 |
| Eduardo Santos | rm373573 |

## Links

| Item | Link |
|---|---|
| Vídeo de apresentação (até 10 min) | a preencher |
| Documentação da arquitetura | <https://github.com/hackathon-fiap-soat/fiapx-docs> |
| Front-end publicado | a preencher (URL do S3 static website) |
| Organização no GitHub | <https://github.com/hackathon-fiap-soat> |

## Repositórios

| Repositório | Conteúdo |
|---|---|
| [`fiapx-docs`](https://github.com/hackathon-fiap-soat/fiapx-docs) | Documentação, ADRs, RFCs, contratos e OpenAPI |
| [`fiapx-infra`](https://github.com/hackathon-fiap-soat/fiapx-infra) | Terraform da AWS, script de criação dos databases e ambiente local |
| [`fiapx-auth`](https://github.com/hackathon-fiap-soat/fiapx-auth) | Cadastro, login e authorizer (Lambdas Node.js) |
| [`fiapx-video-api`](https://github.com/hackathon-fiap-soat/fiapx-video-api) | API de vídeos e orquestração da SAGA (Laravel) |
| [`fiapx-video-processor`](https://github.com/hackathon-fiap-soat/fiapx-video-processor) | Worker de extração de frames (Laravel + ffmpeg, KEDA) |
| [`fiapx-notification`](https://github.com/hackathon-fiap-soat/fiapx-notification) | E-mails por SMTP (Brevo) e histórico no DynamoDB |
| [`fiapx-web`](https://github.com/hackathon-fiap-soat/fiapx-web) | Front-end React |

O usuário `soat-architecture` tem acesso de leitura a todos os repositórios.

## Resumo da solução

A FIAP X recebe vídeos, extrai um frame por segundo e devolve um zip. Reconstruímos o protótipo como uma
solução distribuída na AWS, implantada numa conta da AWS Academy Learner Lab
([ADR-019](../04-adrs/ADR-019-deploy-na-aws-academy-learner-lab.md)):

- O vídeo vai direto do navegador para o S3, com POST pré-assinado.
- O evento do S3 inicia uma SAGA orquestrada no `fiapx-video-api`, que valida o upload, reserva a cota
  do usuário e pede o processamento por fila (SQS).
- Workers no EKS, escalados pelo KEDA de 1 a 10 pods conforme a fila, extraem os frames com `ffmpeg` e
  sobem o zip no S3.
- Em caso de falha, a saga compensa os passos anteriores e envia um e-mail ao usuário por SMTP (Brevo).
- Cadastro e login ficam em Lambdas Node.js atrás do API Gateway, com JWT RS256 validado por um
  Lambda Authorizer.
- O front-end React é um site estático no S3 (static website) que chama o API Gateway com CORS.

## Requisitos atendidos

| Requisito | Como | Evidência |
|---|---|---|
| RF1 — vários vídeos ao mesmo tempo | KEDA escala o worker pela fila | a preencher (k6 + réplicas no dashboard) |
| RF2 — nenhuma requisição perdida | S3 → SQS, outbox, DLQ, idempotência | a preencher (DLQs vazias após o k6) |
| RF3 — usuário e senha | API Gateway + Lambdas + authorizer | a preencher |
| RF4 — listagem de status | `GET /api/videos` | a preencher |
| RF5 — notificação de erro | SAGA → SQS → Lambda → SMTP (Brevo) | a preencher (e-mail recebido + item no DynamoDB) |
| RT1 a RT5 | Aurora, DynamoDB e S3; EKS, KEDA e serviços gerenciados; GitHub; testes ≥ 80% + BDD + Sonar; GitHub Actions | a preencher (cobertura, Sonar, pipelines) |

## Arquitetura

Visão de containers: [`03-arquitetura/c4-containers.md`](../03-arquitetura/c4-containers.md).
Decisões: [ADRs](../04-adrs/README.md) e [RFCs](../05-rfcs/README.md).

## Script de criação do banco e dos recursos

- Databases e usuários: `fiapx-infra/sql/create-databases.sql`.
- Tabelas: migrations de cada serviço; schema consolidado em
  [`03-arquitetura/modelo-de-dados.md`](../03-arquitetura/modelo-de-dados.md).
- Demais recursos: Terraform em `fiapx-infra` e nas pastas `infra/` do `fiapx-auth` e do
  `fiapx-notification`.

## Evidências

A preencher na Etapa 10: prints de cobertura de testes, SonarCloud, pipelines verdes, dashboard do New
Relic, métricas das filas no CloudWatch, resultado do k6 e e-mail de falha recebido.
