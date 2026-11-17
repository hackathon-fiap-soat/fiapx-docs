# RFCs

Cada RFC segue o formato **Resumo, Motivação, Proposta, Alternativas (tabela comparativa), Riscos e
Decisão**, e a decisão aprovada é registrada no ADR indicado em [`04-adrs`](../04-adrs/).
Custos citados são estimativas qualitativas ou aproximadas; a fonte da verdade é a especificação do projeto.

> **Atualização ([ADR-019](../04-adrs/ADR-019-deploy-na-aws-academy-learner-lab.md)):** as RFCs são
> propostas históricas e não foram reescritas. O deploy na AWS Academy Learner Lab alterou o resultado de
> quatro delas: **RFC-001** (sem bootstrap nem OIDC; o workflow cria o bucket do state e usa as credenciais
> do lab), **RFC-008** (o e-mail sai por SMTP externo, Brevo, no lugar do SES; o registro no DynamoDB
> continua), **RFC-009** (front-end em S3 static website com CORS no API Gateway, no lugar do CloudFront) e
> **RFC-010** (sem CloudWatch Metric Streams; métricas de SQS, DLQs, Aurora e API Gateway no CloudWatch).

| RFC | Tema | Decisão resumida | ADR |
| --- | --- | --- | --- |
| 001 | [Escolha da cloud e da IaC](RFC-001-cloud-e-iac.md) | AWS + Terraform ≥ 1.10, backend S3 com lock nativo e saídas no SSM | ADR-002 |
| 002 | [Upload de arquivos grandes](RFC-002-upload-de-arquivos-grandes.md) | POST pré-assinado direto ao S3 (até 500 MB) e SAGA iniciada pelo evento do S3 | ADR-006 |
| 003 | [Estratégia da SAGA](RFC-003-estrategia-da-saga.md) | SAGA orquestrada no `fiapx-video-api` com outbox, idempotência e BDD | ADR-008 |
| 004 | [Autenticação](RFC-004-autenticacao.md) | API Gateway + Lambdas Node.js 24, bcrypt e JWT RS256 com Lambda Authorizer | ADR-004 |
| 005 | [Escala do processamento](RFC-005-escala-do-processamento.md) | Worker Laravel no EKS, 1 vídeo por pod, KEDA pela fila (1–10) | ADR-009 |
| 006 | [Mensageria](RFC-006-mensageria.md) | Amazon SQS (Standard + FIFO + DLQ) no lugar de RabbitMQ/Kafka | ADR-007 |
| 007 | [Banco de dados e cache](RFC-007-banco-de-dados-e-cache.md) | Aurora MySQL Serverless v2, um database por serviço, sem Redis | ADR-005 |
| 008 | [Registro de notificações](RFC-008-registro-de-notificacoes.md) | DynamoDB (PK `email`, SK `message_id`) para histórico e idempotência | ADR-013 |
| 009 | [Hospedagem do front-end](RFC-009-hospedagem-do-front-end.md) | S3 privado + CloudFront com OAC e `/api/*` na mesma origem | ADR-014 |
| 010 | [Observabilidade](RFC-010-observabilidade.md) | New Relic (APM, K8s, Lambdas, logs e alertas) no lugar de Prometheus + Grafana | ADR-011 |
