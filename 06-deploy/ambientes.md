# Ambientes

| Ambiente | Onde | Para quê |
|---|---|---|
| `local` | Máquina de cada integrante, com `docker compose` | Desenvolvimento, testes de integração e testes do Terraform no LocalStack |
| `prod` | Conta da AWS Academy Learner Lab, região `us-east-1` ([ADR-019](../04-adrs/ADR-019-deploy-na-aws-academy-learner-lab.md)) | Demonstração, teste de carga e gravação do vídeo |

Não há ambiente de homologação: o custo do EKS, do NAT e do Aurora dobraria. A qualidade antes do
`prod` vem dos testes no PR e do ambiente local.

## Local

Definido em `fiapx-infra/local/docker-compose.yml`. Como subir, credenciais e a lista completa de
recursos estão no [README do `fiapx-infra`](https://github.com/hackathon-fiap-soat/fiapx-infra#como-rodar-o-ambiente-local).

```bash
cd fiapx-infra/local
docker compose up -d --wait   # sobe e espera os scripts de init
./scripts/verificar.sh        # confere os recursos e roda o teste de fumaça
```

| Serviço | Imagem | Substitui | Endereço |
|---|---|---|---|
| MySQL | `mysql:8.0` | Aurora MySQL | `localhost:3306` |
| LocalStack | `localstack/localstack:4.14.0` (S3, SQS, SSM, Secrets Manager, DynamoDB, Lambda, API Gateway, IAM) | Serviços AWS | `http://localhost:4566` |
| Mailpit | `axllent/mailpit:v1.33.1` | Provedor SMTP (o `fiapx-notification` usa o mesmo adaptador SMTP, apontado para `mailpit:1025` sem autenticação) | UI `http://localhost:8025`, SMTP `localhost:1025` |

Containers de outros repositórios entram na rede `fiapx_default` e chegam ao LocalStack pelo host `localstack`.
As URLs que o LocalStack devolve (ex.: filas em `sqs.us-east-1.localhost.localstack.cloud`) também funcionam
de dentro dessa rede, porque o compose dá esses nomes como alias ao container.

O LocalStack está fixado na `4.14.0`, a última versão Community que roda sem `LOCALSTACK_AUTH_TOKEN`
(as versões `2026.x` exigem conta). Ele não guarda estado: os recursos são recriados a cada subida.

Os scripts de `fiapx-infra/local/init/` rodam o mesmo `sql/create-databases.sql` da AWS e criam o bucket,
as filas e DLQs, a notificação S3 → SQS, a tabela de notificações, os segredos e os
[parâmetros SSM](parametros-ssm.md) com os mesmos nomes de produção (`/fiapx/local/...`). Assim o código
é o mesmo nos dois ambientes; só muda o endpoint da AWS (`AWS_ENDPOINT_URL=http://localhost:4566`).

O EKS não é simulado localmente: o `video-api` e o `video-processor` rodam como containers no compose
(ou direto com `php artisan`), e o KEDA só é exercitado em `prod`.

Terraform local: `tflocal` com state em `.terraform-local/` (no `.gitignore`).

## Produção (AWS Academy Learner Lab)

O `prod` roda numa conta da AWS Academy Learner Lab, com as restrições e escolhas do
[ADR-019](../04-adrs/ADR-019-deploy-na-aws-academy-learner-lab.md): sem roles próprias (tudo usa a
`LabRole`), sem SES nem CloudFront, sem spot, sem `db.serverless`, sem bucket público (Block Public Access da
conta) e com credenciais temporárias.

| Recurso | Configuração |
|---|---|
| Região | `us-east-1` |
| Rede | VPC em 2 AZs, 1 NAT Gateway |
| EKS | 1 managed node group **on-demand** `t3.large` (2 vCPU, 8 GiB), mínimo 2 e máximo 4 nós (8 vCPUs no teto, abaixo do limite do lab de 32 vCPUs e 9 instâncias); cluster e nós com a `LabRole`; launch template com `http_put_response_hop_limit = 2` para os pods usarem a `LabRole` pelo IMDS. Add-ons: AWS Load Balancer Controller, metrics-server, KEDA (`identityOwner: keda`), New Relic `nri-bundle` |
| Aurora | MySQL 8.0 provisionado `db.t3.medium`, uma instância (sem Multi-AZ, Enhanced Monitoring nem Performance Insights); o lab nega `db.serverless`. A classe é a variável `aurora_instance_class` |
| Front-end | Pod nginx (`nginxinc/nginx-unprivileged`) com o build do Vite, imagem no ECR `fiapx-web`, no target group `fiapx-prod-web` do ALB interno (padrão do listener). Acesso pela URL HTTPS do API Gateway (rota `$default`), na mesma origem da API |
| Buckets S3 | A SCP do lab nega `s3:GetBucketObjectLockConfiguration`; os buckets são criados e apagados pelo AWS CLI dentro do Terraform (módulo `s3-bucket`) e as configurações seguem em recursos `aws_s3_bucket_*` |
| E-mail | SMTP externo (OCI Email Delivery, `smtp.email.sa-saopaulo-1.oci.oraclecloud.com:587`, STARTTLS) |
| State do Terraform | Bucket `fiapx-tfstate-<account_id>`, criado pelo próprio workflow, lock nativo do S3 |
| Prefixo dos recursos | `fiapx-prod-*` |
| Parâmetros | `/fiapx/prod/...` no SSM |

## Sessão do lab e credenciais

As credenciais da conta são temporárias (`AWS_SESSION_TOKEN`) e valem enquanto a sessão do lab estiver
aberta (~4 h). Elas ficam em GitHub Secrets **da organização** `hackathon-fiap-soat` (ou de cada
repositório, se não houver acesso de admin), nunca em Variables:

| Secret | Origem |
|---|---|
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` | *AWS Details* da sessão do lab |
| `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | credencial SMTP gerada no OCI Email Delivery (só no `fiapx-notification`) |

Procedimento de cada sessão:

1. Iniciar a sessão no AWS Academy (*Start Lab*) e esperar o indicador ficar verde.
2. Abrir *AWS Details* e copiar `aws_access_key_id`, `aws_secret_access_key` e `aws_session_token` para os
   três Secrets do GitHub.
3. Rodar o `deploy-all.yml` no `fiapx-infra` (~30 min, cabe numa sessão de 4 h) ou fazer os merges do dia.
4. Um job com credencial vencida falha na primeira chamada (`ExpiredToken`): atualizar os Secrets e
   reexecutar o job.
5. Ao terminar a demonstração, rodar o `destroy-all.yml`. Ao fim da sessão o lab pode **parar** os nós do
   EKS, mas EKS, NAT, ALB e Aurora continuam cobrando.

## Custos

Com tudo ligado, o custo estimado é de **~US$ 10/dia**, abatido do crédito do lab:

| Item | Custo aproximado por dia |
|---|---|
| EKS (control plane) | ~US$ 2,40 |
| Nós do EKS (2× `t3.large` on-demand) | ~US$ 4,00 |
| Aurora `db.t3.medium` (uma instância) | ~US$ 2,00 |
| NAT Gateway | ~US$ 1,10 + tráfego |
| ALB interno | ~US$ 0,55 |
| SQS, S3, Lambda, DynamoDB, API Gateway, CloudWatch | centavos no volume do hackathon |
| E-mail (OCI Email Delivery, camada gratuita) | zero |

Valores aproximados, para orientar a decisão de manter o ambiente desligado fora das demonstrações.

## Restrições conhecidas do lab

Encontradas nos primeiros `apply` (2026-11-17) e já tratadas no código. Toda infraestrutura nova deve ser
conferida contra elas antes do PR:

| Restrição | Sintoma | Como o projeto lida |
|---|---|---|
| Sem OIDC, sem criar roles | `iam:CreateRole` negado | credenciais do lab em Secrets; tudo usa a `LabRole` (ADR-019) |
| `LabRole` não confia em `pods.eks` nem em Metric Streams | sem Pod Identity, sem métricas da AWS no New Relic | pods e KEDA usam a credencial do nó (IMDS com 2 saltos) |
| SES, CloudFront, Route 53 Domains negados | `AccessDenied` | SMTP externo (OCI Email Delivery); site no EKS atrás do API Gateway |
| Block Public Access da conta | `PutBucketPolicy` público negado | nenhum bucket público |
| SCP nega `s3:GetBucketObjectLockConfiguration` | `aws_s3_bucket` falha ao ler o bucket | buckets criados pelo AWS CLI no módulo `s3-bucket` |
| `db.serverless` negado; RDS até `medium` | `rds:CreateDBInstance` negado | Aurora `db.t3.medium` |
| Spot e instâncias acima de `large` negados | `UnauthorizedOperation` | nós `t3.large` on-demand |
| Chave `aws/dynamodb` inutilizável | `KMS key ... does not exist` no `CreateTable` | tabela com a criptografia padrão (chave da AWS) |
| Descrição de security group só ASCII | `Character sets beyond ASCII are not supported` | descrições sem acento |

Problemas que não são do lab, mas só aparecem na AWS (o LocalStack não cobre):

| Problema | Sintoma | Correção |
|---|---|---|
| Permissão do authorizer num HTTP API | 500 em rota autenticada; access log: *doesn't have permissions to call the authorizer* | `source_arn` = `<execution_arn>/authorizers/<id>`, sem stage |
| `runAsNonRoot` com `USER` por nome | `CreateContainerConfigError`: *non-numeric user* | `USER 82:82` (UID numérico) no Dockerfile |
| Webhook do Load Balancer Controller | `x509: certificate signed by unknown authority` ao criar Service | `keepTLSSecret=true` e add-ons dependendo do controller |
| Release do Helm que falhou | `cannot re-use a name that is still in use` | `atomic = true` nos charts |

**Checagem antes do PR de infraestrutura nova:**

- Permissões: `aws iam simulate-principal-policy --policy-source-arn arn:aws:iam::<conta>:role/voclabs
  --action-names <ações>`, e o mesmo com `role/LabRole` para o que roda nos pods e nas Lambdas. Uma negação
  explícita (`explicitDeny`) é real. Uma `implicitDeny` pode ser falso negativo de regra com condição, então
  confira com o recurso real.
- Criptografia: não pedir chave KMS gerenciada (`aws/<serviço>`) sem antes verificar que outro recurso na
  conta já a usa.
- Diagnóstico depois de uma falha: access log do API Gateway (`/aws/apigateway/fiapx-prod`), logs das
  Lambdas, `kubectl describe pod` e eventos do namespace.

## Desligar e religar

Para não consumir o crédito do lab, o ambiente `prod` é destruído fora das demonstrações:

1. Com a sessão do lab aberta e os Secrets atualizados, rodar o workflow manual `destroy-all.yml` no
   `fiapx-infra`, digitando a confirmação `destroy-prod`.
2. O workflow desliga a proteção do Aurora (`protect=false`) e derruba tudo na ordem inversa da subida: front-end, aplicações do EKS, Lambdas e por fim a
   infraestrutura ([ADR-018](../04-adrs/ADR-018-orquestracao-do-deploy-no-github-actions.md)).
3. Fica de pé só o bucket do state (`fiapx-tfstate-<account_id>`).

Para religar, rodar o workflow manual `deploy-all.yml` no `fiapx-infra`, digitando `deploy-prod`. Ele
segue a [ordem de deploy](fluxo-de-deploy.md#ordem-entre-repositórios-primeira-subida) e termina com o
smoke test ponta a ponta. Como o tópico SNS dos alarmes é recriado a cada subida, cada integrante confirma
de novo a assinatura no e-mail que a AWS envia.
