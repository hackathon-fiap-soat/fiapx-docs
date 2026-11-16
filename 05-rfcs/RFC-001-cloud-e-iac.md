# RFC-001 — Escolha da cloud e da IaC

- **Status:** Aprovada
- **Data:** 2026-11-16
- **Autores:** Diego Fenille, Eduardo Santos
- **ADR resultante:** ADR-002

## Resumo

Propomos hospedar o FIAP X na **AWS** (região padrão `us-east-1`, configurável) e descrever toda a
infraestrutura em **Terraform** (≥ 1.10), com backend remoto em S3 e lock nativo (`use_lockfile = true`).
A infraestrutura compartilhada fica no `fiapx-infra`; cada serviço versiona a própria parte em `infra/`
e lê as saídas compartilhadas do SSM Parameter Store (`/fiapx/<env>/...`).

## Motivação

O enunciado pede persistência, arquitetura escalável e um "script de criação do banco de dados e demais
recursos". A solução precisa de Kubernetes gerenciado, funções serverless, fila durável, armazenamento de
objetos, banco relacional gerenciado e envio de e-mail. Tudo isso deve ser criado de forma reproduzível
(para subir antes da demonstração e destruir depois, por custo) e por pipeline (GitHub Actions com OIDC).

O time já operou nas Fases 3 e 4 um ambiente AWS (EKS, RDS MySQL, API Gateway, Lambda de autenticação)
criado com Terraform e backend S3. Reaproveitar esse conhecimento reduz o risco de entrega no prazo do
hackathon.

## Proposta

- **Cloud:** AWS, com os serviços gerenciados EKS, Aurora MySQL Serverless v2, S3, SQS, Lambda, API Gateway
  (HTTP API), SES, DynamoDB, CloudFront, ECR, Secrets Manager e SSM Parameter Store.
- **IaC:** Terraform ≥ 1.10 com backend S3 (bucket versionado e criptografado) e `use_lockfile = true`,
  dispensando a tabela DynamoDB de lock usada na Fase 3.
- **Bootstrap:** `fiapx-infra/bootstrap/` roda uma única vez, com state local, e cria o bucket do state e
  as roles OIDC do GitHub (uma por repositório).
- **Módulos:** `network`, `eks`, `eks-addons`, `aurora`, `storage`, `messaging`, `ses`, `ecr`, `edge`,
  `web-hosting` e `ssm-outputs`, compostos em `envs/prod/`.
- **Desacoplamento entre repositórios:** saídas publicadas no SSM (por exemplo `/fiapx/prod/aurora/endpoint`
  e `/fiapx/prod/sqs/<fila>/url`), sem `terraform_remote_state`.
- **Apply:** somente pelo GitHub Actions no merge da `main` (environment `prod`); apply local apenas no
  LocalStack ou, quando indispensável, na AWS real seguindo a política da ADR-016.
- **Ambiente local:** `fiapx-infra/local/docker-compose.yml` com MySQL 8.0, LocalStack e Mailpit, para que o
  desenvolvimento não dependa da conta AWS.

## Alternativas

| Critério | AWS + Terraform (proposta) | GCP + Terraform | Azure + Terraform/Bicep | AWS + CloudFormation/CDK |
| --- | --- | --- | --- | --- |
| Serviços necessários (K8s, função, fila, objetos, SQL, e-mail) | Todos nativos (EKS, Lambda, SQS, S3, Aurora, SES) | Quase todos (GKE, Cloud Run/Functions, Pub/Sub, GCS, Cloud SQL); sem e-mail transacional nativo | Quase todos (AKS, Functions, Service Bus, Blob, Azure SQL/MySQL); e-mail via Communication Services | Os mesmos da AWS |
| Experiência do time | Alta (Fases 3 e 4) | Baixa | Baixa | Média (só a AWS; a ferramenta é nova) |
| Curva de aprendizado | Baixa | Alta | Alta | Média (CDK em TypeScript ou YAML extenso) |
| Custo aproximado do hackathon | Médio (EKS ~US$ 73/mês, NAT, Aurora); mitigado com `terraform destroy` | Médio (GKE Autopilot pode ser mais barato) | Médio | Igual à AWS |
| Complexidade operacional | Média | Média | Média | Média |
| Lock-in da IaC | Baixo: HCL, ferramenta multi-cloud | Baixo | Baixo (Terraform) / alto (Bicep) | Alto: só AWS |
| State e lock | Backend S3 com lock nativo | Backend GCS | Backend Azure Storage | Gerenciado pela própria AWS (stacks) |
| Ambiente local | LocalStack + `tflocal` | Emuladores parciais | Azurite e emuladores parciais | LocalStack (CDK local) |
| Aderência ao enunciado | Atende (cloud é livre; pede escalabilidade e scripts de criação) | Atende | Atende | Atende |

## Riscos

- **Custo da conta:** EKS, NAT Gateway e Aurora geram custo contínuo. Mitigação: `destroy.yml` manual
  com confirmação digitada, ambiente ligado só nas demonstrações e desenvolvimento no LocalStack.
- **Lock-in nos serviços gerenciados** (SQS, SES, Lambda). Mitigação: portas e adapters da Clean
  Architecture (`ObjectStorage`, `CommandBus`, `EmailSender`) isolam o SDK da AWS do domínio.
- **Limites de conta nova** (sandbox do SES, cotas de vCPU do EKS). Mitigação: pedir aumento cedo e
  registrar no ADR correspondente.
- **Drift por apply local.** Mitigação: lock nativo no mesmo backend e registro no PR do que foi aplicado.

## Decisão

Aprovada: AWS como cloud única e Terraform ≥ 1.10 como IaC, com backend S3 e lock nativo, bootstrap
separado e saídas no SSM Parameter Store. A decisão é registrada na **ADR-002**.
