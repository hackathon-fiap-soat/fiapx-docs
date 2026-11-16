# fiapx-docs

Documentação do FIAP X: Domain Storytelling, C4, sequências, SAGA, ADRs, RFCs, fluxo de deploy, contratos de mensagens (JSON Schema), OpenAPI e documento de entrega.

> Parte do **Hackathon FIAP X — Processador de Vídeos** (PÓS TECH SOAT, Fase 5).
> 🚧 Em construção. A documentação vem antes do código: a arquitetura, as decisões (ADRs/RFCs) e os
> contratos ficam em [`fiapx-docs`](https://github.com/hackathon-fiap-soat/fiapx-docs).

## Stack

Markdown + Mermaid + JSON Schema + OpenAPI

## Como rodar

_A definir nas próximas etapas do plano._

## Repositórios do projeto

| Repositório | Responsabilidade |
|---|---|
| [`fiapx-docs`](https://github.com/hackathon-fiap-soat/fiapx-docs) | Documentação do FIAP X: Domain Storytelling, C4, sequências, SAGA, ADRs, RFCs, fluxo de deploy, contratos de mensagens (JSON Schema), OpenAPI e documento de entrega. |
| [`fiapx-infra`](https://github.com/hackathon-fiap-soat/fiapx-infra) | Infraestrutura do FIAP X: VPC, EKS (add-ons), Aurora MySQL, S3, SQS/DLQ, SES, ECR, API Gateway + VPC Link + ALB interno, Secrets, OIDC do GitHub, outputs no SSM e ambiente local (docker-compose + LocalStack). |
| [`fiapx-auth`](https://github.com/hackathon-fiap-soat/fiapx-auth) | Autenticação do FIAP X: Lambdas de register, login e authorizer (JWT RS256) e rotas /api/auth/* no API Gateway. |
| [`fiapx-video-api`](https://github.com/hackathon-fiap-soat/fiapx-video-api) | Aplicação principal do FIAP X: gestão de vídeos, POST pré-assinado no S3, listagem de status, download e orquestração da SAGA (outbox e consumidores idempotentes). |
| [`fiapx-video-processor`](https://github.com/hackathon-fiap-soat/fiapx-video-processor) | Worker do FIAP X: consome ProcessVideo/CleanupArtifacts, extrai 1 frame por segundo com ffmpeg, gera o zip no S3 e responde à SAGA. Escalado por KEDA. |
| [`fiapx-notification`](https://github.com/hackathon-fiap-soat/fiapx-notification) | Notificação do FIAP X: fila SQS → Lambda que envia e-mail via SES, registra cada envio no DynamoDB (chave = e-mail) e responde à SAGA. |
| [`fiapx-web`](https://github.com/hackathon-fiap-soat/fiapx-web) | Front-end do FIAP X: cadastro, login, upload de vários vídeos, lista de status e download do zip. Servido por S3 + CloudFront. |

## Contribuição

- A branch `main` é protegida: toda mudança entra por Pull Request com revisão de um code owner.
- Nunca commitar segredos (`.env`, chaves, tokens). Use `.env.example` com valores fictícios.

## Licença

[MIT](LICENSE)
