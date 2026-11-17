# ADR-019 — Deploy na AWS Academy Learner Lab: credenciais do lab, LabRole, SMTP externo e site em S3 website

- **Status:** Aceito
- **Data:** 2026-11-16
- **Decisores:** Diego Fenille, Eduardo Santos
- **Relacionados:** [ADR-002](ADR-002-aws-e-terraform-com-backend-s3-e-lock-nativo.md), [ADR-005](ADR-005-aurora-mysql-serverless-v2-um-database-por-servico.md), [ADR-009](ADR-009-worker-laravel-no-eks-escalado-por-keda.md), [ADR-011](ADR-011-observabilidade-com-new-relic.md), [ADR-012](ADR-012-ci-cd-com-github-actions-oidc-e-ordem-de-deploy.md), [ADR-013](ADR-013-notificacao-sqs-lambda-ses-e-historico-no-dynamodb.md), [ADR-014](ADR-014-front-end-react-vite-em-s3-cloudfront-mesma-origem.md), [ADR-015](ADR-015-remetente-de-email-dominio-proprio-e-sandbox-do-ses.md), [ADR-016](ADR-016-terraform-apply-somente-via-github-actions.md), [ADR-018](ADR-018-orquestracao-do-deploy-no-github-actions.md)
- **Substitui:** ADR-015 por inteiro; ADR-012, ADR-013, ADR-014 e ADR-016 nos pontos listados abaixo

## Contexto

O ambiente `prod` roda numa conta da **AWS Academy Learner Lab**, não numa conta própria do time. A conta
foi verificada em 2026-11-16 com as credenciais do lab, apenas com leituras e `--dry-run`:

| Item | Resultado na conta |
|---|---|
| Identidade | `assumed-role/voclabs/...`; credenciais temporárias (`AWS_SESSION_TOKEN`) que expiram com a sessão do lab (~4 h) |
| IAM | não cria roles, usuários nem provedor OIDC (só service-linked roles). Existe a **`LabRole`** (instance profile `LabInstanceProfile`) |
| Confiança da `LabRole` | `ec2`, `eks`, `lambda`, `firehose`, `rds`, `apigateway`, `elasticloadbalancing` e outros. **Não** inclui `pods.eks.amazonaws.com` (Pod Identity), `streams.metrics.cloudwatch.amazonaws.com` (Metric Streams) nem o GitHub |
| EC2 | `t3.medium`, `t3.large`, `m5.large`, `c5.large` permitidos; `t3.xlarge` negado; **spot negado**. O lab documenta teto de 32 vCPUs e 9 instâncias por região |
| Aurora MySQL 8.0 | `db.serverless`, `db.t3.medium`, `db.t4g.medium` disponíveis; o lab não suporta Multi-AZ nem Enhanced Monitoring |
| **SES** | **negado** (v1 e v2, `us-east-1` e `us-west-2`) |
| **CloudFront** | **negado** |
| Route 53 Domains | negado (hosted zones são permitidas) |
| EKS, API Gateway (HTTP API e VPC Link), ECR, SQS, S3, DynamoDB, SSM, Secrets Manager, Firehose, SNS, ELB, CloudWatch | permitidos |

Isso inviabiliza quatro decisões já aceitas: OIDC com uma role por repositório (ADR-012), roles próprias
com menor privilégio por serviço ([seguranca.md](../03-arquitetura/seguranca.md)), e-mail pelo SES com domínio
próprio (ADR-013 e ADR-015) e front-end no CloudFront com `/api/*` na mesma origem (ADR-014).

## Decisão

### 1. Credenciais do lab em GitHub Secrets (no lugar do OIDC)

- Secrets **da organização** `hackathon-fiap-soat` (ou de cada repositório, se não houver acesso de admin):
  `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` e `AWS_SESSION_TOKEN`. **Nunca Variables**: os repositórios
  são públicos e Variables não são mascaradas nos logs.
- A cada nova sessão do lab, quem vai fazer o deploy copia as credenciais de *AWS Details* para os Secrets.
  Um job com credencial vencida falha na primeira chamada (`ExpiredToken`); basta atualizar e reexecutar.
- Os workflows usam `aws-actions/configure-aws-credentials` com essas três chaves e região `us-east-1`.
- O resto do ADR-012 continua: pipeline por repositório, ordem de deploy e checks de PR.

### 2. Sem bootstrap manual: o workflow cria o bucket do state

- Não existe mais `fiapx-infra/bootstrap/` (não há roles OIDC para criar). O primeiro passo de todo job
  Terraform garante, de forma idempotente, o bucket **`fiapx-tfstate-<account_id>`** (versionado, SSE-S3,
  Block Public Access) e passa o nome no `terraform init -backend-config=bucket=...`. O lock continua nativo
  do S3 (`use_lockfile`), como no ADR-002.
- Com isso, **todo** `apply` é feito pelo GitHub Actions, sem a exceção do bootstrap do ADR-016.

### 3. `LabRole` para tudo o que precisa de identidade

| Quem | Antes | Agora |
|---|---|---|
| Cluster EKS | role do cluster criada pelo Terraform | `LabRole` |
| Nós do EKS | role dos nós | `LabRole` (instance profile do node group) |
| Pods do video-api e do processor | role própria por EKS Pod Identity | credenciais da `LabRole` dos nós, pelo IMDS (launch template com `http_put_response_hop_limit = 2`) |
| KEDA | identidade do workload (`identityOwner: workload`) | identidade do operador (`identityOwner: keda`), que também usa a `LabRole` dos nós |
| AWS Load Balancer Controller | role por Pod Identity | `LabRole` dos nós |
| Lambdas do auth e da notificação | role de execução por Lambda | `LabRole` |

O Terraform lê o ARN com `data "aws_iam_role" "lab" { name = "LabRole" }` e não cria nenhuma role. O acesso
ao cluster (`kubectl`/Helm no GitHub Actions) é do criador do cluster: a role `voclabs`, a mesma das
credenciais do lab.

### 3.1 Migrations do `fiapx-auth` pela Lambda `migrate`

O Aurora fica em subnet privada e o runner do GitHub não o alcança. O `fiapx-auth` ganha uma quinta Lambda,
`migrate`, na VPC e sem rota no API Gateway; o `deploy.yml` a invoca depois do `apply` e falha se ela
devolver erro. O `fiapx-video-api` continua com o Job `migrate` no EKS, e os databases e usuários são criados
por um Job do `fiapx-infra` (`sql/create-databases.sql`) dentro do cluster.

### 4. Capacidade dentro dos limites do lab

- Node group **on-demand** com `t3.large` (2 vCPU, 8 GiB), mínimo 2 e máximo 4 nós (8 vCPUs no teto),
  abaixo do limite de 32 vCPUs e 9 instâncias. Nada de spot.
- Aurora MySQL 8.0 **Serverless v2** de 0,5 a 2 ACU, uma instância só (sem Multi-AZ, sem Enhanced
  Monitoring, sem Performance Insights). Se o lab recusar `db.serverless` no primeiro `apply`, a variável
  `aurora_instance_class = "db.t4g.medium"` troca para instância provisionada sem mudar mais nada.

### 5. E-mail por SMTP externo (no lugar do SES)

- A Lambda de notificação envia por **SMTP autenticado** (Nodemailer) num provedor externo. O padrão é o
  **Brevo** (`smtp-relay.brevo.com:587`, STARTTLS, plano gratuito de 300 e-mails/dia); qualquer provedor
  SMTP serve, porque host, porta, usuário, senha e remetente são configuração.
- O remetente (`SMTP_FROM`) é um e-mail do time verificado no provedor (single sender). Não há domínio
  próprio, Route 53, DKIM/SPF/DMARC nem sandbox do SES: **o ADR-015 deixa de valer**.
- As credenciais vêm dos GitHub Secrets `SMTP_USER`, `SMTP_PASSWORD` e `SMTP_FROM`; o Terraform do
  `fiapx-notification` grava tudo num secret do Secrets Manager (`fiapx/<env>/notification/smtp`), lido pela
  Lambda na inicialização. Host e porta ficam no SSM.
- Localmente nada muda: o mesmo adaptador SMTP aponta para o Mailpit (`mailpit:1025`, sem autenticação).
- O resto do ADR-013 continua: SQS → Lambda → e-mail, histórico e idempotência no DynamoDB. O handler
  opcional de eventos do SES (bounces) deixa de existir; uma falha de envio vira `NotificationFailed`.

### 6. Front-end em S3 static website (no lugar do CloudFront)

- O build do `fiapx-web` vai para o bucket `fiapx-<env>-web-<account_id>` com **website hosting** e leitura
  pública só de objetos (`s3:GetObject`). URL: `http://<bucket>.s3-website-us-east-1.amazonaws.com`.
  `index.html` também é o documento de erro, para o roteamento do React funcionar em qualquer caminho.
- Site e API ficam em **origens diferentes**. Por isso:
  - o HTTP API do API Gateway ganha **CORS** com origem igual à URL do site, métodos `GET, POST, PUT,
    DELETE, OPTIONS` e headers `Authorization, Content-Type, X-Correlation-Id`. O preflight `OPTIONS` é
    respondido pelo API Gateway antes do authorizer;
  - o front usa `VITE_API_BASE_URL=<URL do API Gateway>/api`, gerado no deploy a partir do SSM;
  - o CORS do bucket de vídeos usa a URL do site como origem (ADR-006 continua, só muda o domínio).
- O token continua em memória + `sessionStorage` e só trafega para a API, que é HTTPS.
- **Plano B**, só se o lab recusar a bucket policy pública no primeiro `apply`: o site passa a ser um pod
  nginx no EKS, exposto pela rota `$default` do mesmo API Gateway (mesma origem e HTTPS). Essa troca será
  registrada neste ADR.

### 7. Observabilidade sem Metric Streams

- Sem role para o CloudWatch Metric Streams nem para a integração da conta AWS no New Relic. O New Relic
  fica com APM (Laravel), Kubernetes (`nri-bundle`), logs e Lambdas (extensão do New Relic com a license key).
- As métricas dos serviços gerenciados (SQS, DLQs, Aurora, API Gateway) ficam no **CloudWatch**, com os
  alarmes de DLQ publicando num tópico SNS com assinatura de e-mail do time.

### 8. Operação

- Antes de cada `deploy-all`: iniciar a sessão do lab e atualizar os 3 Secrets. O `deploy-all` leva ~30 min
  e cabe numa sessão de 4 h.
- Ao fim da sessão, o lab pode **parar** as instâncias EC2 (nós do EKS); EKS, NAT, ALB e Aurora continuam
  cobrando. Por isso, ao terminar a demonstração, rodar o `destroy-all` (ADR-018).
- Custo estimado com tudo ligado: ~US$ 10/dia (EKS ~2,40; 2× t3.large ~4,00; Aurora ~1,50; NAT ~1,10; ALB
  ~0,55), abatido do crédito do lab.

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Conta AWS própria do time | Mantém o desenho original, mas o time decidiu usar a conta do Academy (sem custo próprio) |
| Credenciais em GitHub Variables | Repositórios públicos: Variables aparecem em claro nos logs |
| Notificação por SNS com assinatura de e-mail | Cada usuário precisaria confirmar uma assinatura antes; texto sem HTML |
| Mailpit no cluster | O e-mail não chegaria ao usuário de verdade, e o requisito é notificar o usuário |
| Front-end como pod no EKS via API Gateway | Mantém mesma origem e HTTPS, mas o time escolheu o S3 website; fica como plano B |
| Pedir liberação de SES/CloudFront ao Academy | Fora do controle do time e do prazo do hackathon |

## Consequências

### Positivas

- O ambiente sobe e desce inteiro pelo GitHub Actions, sem nenhum passo manual na AWS.
- O código das aplicações quase não muda: só o adaptador de e-mail e a configuração do front.

### Negativas

- **Menor privilégio perdido:** todos os componentes usam a `LabRole`, que tem permissões amplas. As
  políticas de menor privilégio por serviço ficam documentadas em [seguranca.md](../03-arquitetura/seguranca.md)
  como o desenho para uma conta própria, mas não são aplicadas no lab.
- Credenciais de curta duração atualizadas à mão a cada sessão.
- Site em HTTP (sem TLS), sujeito a adulteração no caminho; aceito para a demonstração acadêmica.
- CORS e preflight nas chamadas à API, que a mesma origem evitava.
- Dependência de um provedor SMTP externo e da reputação dele (e-mails podem cair em spam).
- Sem métricas dos serviços gerenciados no New Relic; elas ficam no CloudWatch.
