# ADRs — Architecture Decision Records

Registro das decisões de arquitetura do Hackathon FIAP X, no formato [MADR](https://adr.github.io/madr/) (Markdown Architectural Decision Records).
Cada ADR traz Contexto, Decisão, Alternativas consideradas e Consequências; decisões novas ou que contrariem uma existente viram um ADR novo, e o anterior passa a "Substituído por ADR-NNN".

| ADR | Título | Status | Data |
| --- | --- | --- | --- |
| 001 | [Um repositório por serviço (polyrepo) e comunicação entre repositórios via SSM Parameter Store](ADR-001-polyrepo-e-integracao-via-ssm-parameter-store.md) | Aceito | 2026-11-16 |
| 002 | [AWS como cloud e Terraform como IaC, com backend S3 e lock nativo](ADR-002-aws-e-terraform-com-backend-s3-e-lock-nativo.md) | Aceito, parcialmente substituído por [ADR-019](ADR-019-deploy-na-aws-academy-learner-lab.md) | 2026-11-16 |
| 003 | [DDD + Clean Architecture nos serviços Laravel](ADR-003-ddd-e-clean-architecture-nos-servicos-laravel.md) | Aceito | 2026-11-16 |
| 004 | [Autenticação com API Gateway + Lambda Node.js + Lambda Authorizer e JWT RS256](ADR-004-autenticacao-api-gateway-lambda-authorizer-jwt-rs256.md) | Aceito | 2026-11-16 |
| 005 | [Aurora MySQL Serverless v2 com um database por serviço no mesmo cluster](ADR-005-aurora-mysql-serverless-v2-um-database-por-servico.md) | Aceito, parcialmente substituído por [ADR-019](ADR-019-deploy-na-aws-academy-learner-lab.md) | 2026-11-16 |
| 006 | [Upload direto ao S3 via POST pré-assinado e início da SAGA pelo evento do S3](ADR-006-upload-direto-s3-e-inicio-da-saga-pelo-evento.md) | Aceito | 2026-11-16 |
| 007 | [Amazon SQS como mensageria (Standard para comandos, FIFO para respostas, DLQ em todas)](ADR-007-amazon-sqs-como-mensageria.md) | Aceito | 2026-11-16 |
| 008 | [SAGA orquestrada no video-api com transactional outbox e consumidores idempotentes](ADR-008-saga-orquestrada-com-outbox-e-consumidores-idempotentes.md) | Aceito | 2026-11-16 |
| 009 | [Worker Laravel no EKS escalado por KEDA (1 vídeo por pod, heartbeat de visibility)](ADR-009-worker-laravel-no-eks-escalado-por-keda.md) | Aceito, parcialmente substituído por [ADR-019](ADR-019-deploy-na-aws-academy-learner-lab.md) | 2026-11-16 |
| 010 | [Exposição da API: API Gateway → VPC Link → ALB interno + TargetGroupBinding](ADR-010-api-gateway-vpc-link-alb-interno-e-targetgroupbinding.md) | Aceito, parcialmente substituído por [ADR-019](ADR-019-deploy-na-aws-academy-learner-lab.md) | 2026-11-16 |
| 011 | [Observabilidade com New Relic](ADR-011-observabilidade-com-new-relic.md) | Aceito, parcialmente substituído por [ADR-019](ADR-019-deploy-na-aws-academy-learner-lab.md) | 2026-11-16 |
| 012 | [CI/CD com GitHub Actions + OIDC e ordem de deploy entre repositórios](ADR-012-ci-cd-com-github-actions-oidc-e-ordem-de-deploy.md) | Aceito, parcialmente substituído por [ADR-019](ADR-019-deploy-na-aws-academy-learner-lab.md) | 2026-11-16 |
| 013 | [Notificação: SQS → Lambda Node.js → SES, com histórico e idempotência no DynamoDB (PK `email`, SK `message_id`)](ADR-013-notificacao-sqs-lambda-ses-e-historico-no-dynamodb.md) | Aceito, parcialmente substituído por [ADR-019](ADR-019-deploy-na-aws-academy-learner-lab.md) | 2026-11-16 |
| 014 | [Front-end React + Vite em S3 + CloudFront, com `/api/*` na mesma origem](ADR-014-front-end-react-vite-em-s3-cloudfront-mesma-origem.md) | Aceito, parcialmente substituído por [ADR-019](ADR-019-deploy-na-aws-academy-learner-lab.md) | 2026-11-16 |
| 015 | [Remetente de e-mail: domínio próprio no Route 53 com DKIM/SPF/DMARC e uso do sandbox do SES](ADR-015-remetente-de-email-dominio-proprio-e-sandbox-do-ses.md) | Substituído por [ADR-019](ADR-019-deploy-na-aws-academy-learner-lab.md) | 2026-11-16 |
| 016 | [`terraform apply` somente via GitHub Actions; apply local apenas para testes (§11.5)](ADR-016-terraform-apply-somente-via-github-actions.md) | Aceito, parcialmente substituído por [ADR-019](ADR-019-deploy-na-aws-academy-learner-lab.md) | 2026-11-16 |
| 017 | [Recuperação e troca de senha no `fiapx-auth`, com e-mail pelo `fiapx-notification`](ADR-017-recuperacao-e-troca-de-senha.md) | Aceito | 2026-11-16 |
| 018 | [Orquestração do deploy do ambiente inteiro no GitHub Actions (`fiapx-infra`)](ADR-018-orquestracao-do-deploy-no-github-actions.md) | Aceito | 2026-11-16 |
| 019 | [Deploy na AWS Academy Learner Lab: credenciais do lab, LabRole, SMTP externo e site no EKS](ADR-019-deploy-na-aws-academy-learner-lab.md) | Aceito, provedor de e-mail substituído por [ADR-020](ADR-020-email-pelo-oci-email-delivery.md) | 2026-11-16 |
| 020 | [E-mail pelo OCI Email Delivery no lugar do OCI Email Delivery](ADR-020-email-pelo-oci-email-delivery.md) | Aceito | 2026-11-17 |
