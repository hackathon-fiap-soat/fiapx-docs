# Parâmetros SSM e segredos

Catálogo das chaves que ligam os repositórios
([ADR-001](../04-adrs/ADR-001-polyrepo-e-integracao-via-ssm-parameter-store.md)). O prefixo é
`/fiapx/<env>/`, com `<env>` = `prod` na AWS e `local` no ambiente local. Os nomes são iguais nos dois
ambientes: o código dos serviços muda só o `<env>` e o endpoint da AWS.

Uma chave só muda por PR no repositório que a publica. Uma chave nova é criada antes de a antiga ser
removida.

## Parâmetros

| Chave (`/fiapx/<env>/...`) | Valor | Publicado por | Lido por |
|---|---|---|---|
| `region` | região da AWS | `fiapx-infra` | todos |
| `vpc/private_subnet_ids` | subnets privadas | `fiapx-infra` | `fiapx-auth`, `fiapx-notification` (Lambdas na VPC) |
| `vpc/lambda_security_group_id` | security group das Lambdas na VPC (o do Aurora aceita conexões dele) | `fiapx-infra` | `fiapx-auth`, `fiapx-notification` |
| `eks/cluster_name` | nome do cluster | `fiapx-infra` | `fiapx-video-api`, `fiapx-video-processor` (deploy) |
| `aurora/endpoint`, `aurora/port` | endereço do banco | `fiapx-infra` | `fiapx-auth`, `fiapx-video-api` |
| `aurora/secret_arn` | segredo do usuário master | `fiapx-infra` | só o `fiapx-infra` (criação dos databases) |
| `db/auth/secret_arn` | segredo do usuário `fiapx_auth` | `fiapx-infra` | `fiapx-auth` |
| `db/video/secret_arn` | segredo do usuário `fiapx_video` | `fiapx-infra` | `fiapx-video-api` |
| `auth/jwt_private_key_secret_arn` | segredo da chave privada RSA | `fiapx-infra` | Lambdas `login` e `password` |
| `auth/jwt_public_key` | chave pública RSA (PEM) | `fiapx-infra` | Lambda `authorizer` (o Terraform passa por variável de ambiente), `fiapx-video-api` (lê do SSM em execução: o PEM de várias linhas não cabe no `aws.env`) |
| `auth/authorizer_id` | id do Lambda Authorizer no HTTP API | `fiapx-auth` | `fiapx-video-api` (rotas `/api/videos*`) |
| `s3/videos_bucket` | bucket de vídeos | `fiapx-infra` | `fiapx-video-api`, `fiapx-video-processor` |
| `sqs/video-uploaded/url`, `/arn` | fila de eventos do S3 | `fiapx-infra` | `fiapx-video-api` |
| `sqs/processing-commands/url`, `/arn` | fila de comandos do worker | `fiapx-infra` | `fiapx-video-api`, `fiapx-video-processor` |
| `sqs/saga-replies/url`, `/arn` | fila FIFO de respostas | `fiapx-infra` | `fiapx-video-api`, `fiapx-video-processor`, `fiapx-notification` |
| `sns/alerts_topic_arn` | tópico SNS dos alarmes (assinaturas de e-mail do time) | `fiapx-infra` | `fiapx-notification` (alarme da própria DLQ) |
| `sqs/<fila>-dlq/url` | DLQ de cada fila | `fiapx-infra` e `fiapx-notification` | alarmes, reprocessamento manual |
| `sqs/notification-commands/url`, `/arn` | fila de comandos de e-mail | `fiapx-notification` | `fiapx-video-api`, `fiapx-auth` |
| `dynamodb/notifications/table_name` | histórico de e-mails | `fiapx-notification` | `fiapx-notification` |
| `notification/smtp_host` | host do provedor SMTP (`smtp.email.sa-saopaulo-1.oci.oraclecloud.com`; `mailpit` no local) | `fiapx-notification` | `fiapx-notification` (variável de ambiente da Lambda) |
| `notification/smtp_port` | porta SMTP (`587` com STARTTLS; `1025` no Mailpit) | `fiapx-notification` | `fiapx-notification` |
| `notification/smtp_secret_arn` | ARN do segredo `fiapx/<env>/notification/smtp` | `fiapx-notification` | `fiapx-notification` (a Lambda lê o segredo na inicialização) |
| `apigw/api_id`, `apigw/vpc_link_id` | API Gateway e VPC Link | `fiapx-infra` | `fiapx-auth` (rotas), `fiapx-video-api` e `fiapx-web` (integração; o `fiapx-web` cria a rota `$default`) |
| `apigw/url` | URL base do HTTP API (`https://<api_id>.execute-api.<região>.amazonaws.com`) | `fiapx-infra` | smoke tests dos deploys |
| `alb/target_group_arn` | target group do video-api no ALB interno | `fiapx-infra` | `fiapx-video-api` (`TargetGroupBinding`) |
| `alb/web_target_group_arn` | target group do site (`fiapx-<env>-web`, padrão do listener) | `fiapx-infra` | `fiapx-web` (`TargetGroupBinding`) |
| `alb/listener_arn` | listener do ALB interno | `fiapx-infra` | `fiapx-video-api` e `fiapx-web` (integração das rotas pelo VPC Link) |
| `ecr/<repo>/url` | repositório de imagens | `fiapx-infra` | `fiapx-video-api`, `fiapx-video-processor` |
| `ecr/fiapx-web/url` | repositório da imagem nginx do site | `fiapx-infra` | `fiapx-web` |
| `web/url` | URL do site, que é a URL do API Gateway (`https://<api_id>.execute-api.us-east-1.amazonaws.com`) | `fiapx-infra` | `fiapx-infra` (CORS do bucket de vídeos), `fiapx-web` (smoke), `fiapx-auth` (link de redefinição), `fiapx-notification` (links dos e-mails) |

As chaves de rede, EKS, API Gateway, ALB e ECR existem só em `prod`. No ambiente local, o
init do LocalStack publica as demais, inclusive as `notification/smtp_*` apontando para o Mailpit (no
`prod`, essas três são publicadas pelo `fiapx-notification`).

Não há chaves de SES, CloudFront nem Route 53: o e-mail sai por SMTP externo e o site é um pod nginx no
EKS, servido pela URL do API Gateway ([ADR-019](../04-adrs/ADR-019-deploy-na-aws-academy-learner-lab.md)).

## Segredos (Secrets Manager)

| Nome | Conteúdo | Quem lê |
|---|---|---|
| `fiapx/<env>/auth/jwt-private-key` | chave privada RSA do JWT (PEM) | Lambdas `login` e `password` |
| `fiapx/<env>/db/auth` | JSON `{engine, host, port, username, password, dbname}` | `fiapx-auth` |
| `fiapx/<env>/db/video` | mesmo formato | `fiapx-video-api` |
| `fiapx/<env>/notification/smtp` | JSON `{user, password, from}`, gravado pelo Terraform do `fiapx-notification` a partir dos GitHub Secrets `SMTP_USER`, `SMTP_PASSWORD` e `SMTP_FROM` | Lambda `notification` (na inicialização) |
| `fiapx/<env>/auth/newrelic`, `fiapx/<env>/notification/newrelic` | JSON `{LicenseKey}`, gravado pelo Terraform de cada repositório a partir do GitHub Secret `NEW_RELIC_LICENSE_KEY` (só existe com o Secret preenchido) | extensão do New Relic nas Lambdas (`NEW_RELIC_LICENSE_KEY_SECRET`) |

No ambiente local, a chave RSA é gerada a cada subida do LocalStack, e nenhuma chave fica versionada. O
segredo SMTP local aponta para o Mailpit, sem autenticação (usuário e senha vazios, remetente fictício).

## GitHub Secrets

Valores que não podem ir para o SSM porque são necessários antes de o ambiente existir ou porque o
Terraform os grava no Secrets Manager ([ADR-019](../04-adrs/ADR-019-deploy-na-aws-academy-learner-lab.md)). Sempre **Secrets** (mascarados nos logs), nunca Variables: os
repositórios são públicos.

| Secret | Onde | Uso |
|---|---|---|
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` | organização `hackathon-fiap-soat` (ou cada repositório, sem acesso de admin) | credenciais da sessão da AWS Academy Learner Lab, atualizadas a cada sessão (~4 h) |
| `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | `fiapx-notification` e `fiapx-infra` (o `deploy-all` repassa com `secrets: inherit`) | credenciais do provedor SMTP (OCI Email Delivery) e remetente aprovado; o Terraform grava em `fiapx/<env>/notification/smtp` |
| `NEW_RELIC_LICENSE_KEY` | repositórios que fazem deploy | license key (ingest) do New Relic: `nri-bundle` no cluster (`fiapx-infra`), agente PHP (Secret do Kubernetes no video-api e no processor) e segredo da extensão das Lambdas (auth e notification). Vazio = sem New Relic |
| `NEW_RELIC_ACCOUNT_ID` | `fiapx-auth`, `fiapx-notification` (e `fiapx-infra`, que repassa e usa na stack do New Relic) | id da conta do New Relic, exigido pela extensão das Lambdas e pelo provider Terraform do New Relic |
| `NEW_RELIC_API_KEY` | `fiapx-infra` | **User key** do New Relic (não é a license key): o provider Terraform cria dashboards, alertas e Synthetics (ADR-021) |
| `ALERT_EMAILS` | `fiapx-infra` | lista JSON de e-mails do time (ex.: `["a@exemplo.com"]`): assinaturas do SNS dos alarmes do CloudWatch e destino de e-mail dos alertas do New Relic. Variável `sensitive` |
| `SONAR_TOKEN` | repositórios com código | token do SonarCloud para a análise no CI (Etapa 8) |
