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
| `auth/jwt_public_key` | chave pública RSA (PEM) | `fiapx-infra` | Lambda `authorizer` (o Terraform passa por variável de ambiente), `fiapx-video-api` |
| `auth/authorizer_id` | id do Lambda Authorizer no HTTP API | `fiapx-auth` | `fiapx-video-api` (rotas `/api/videos*`) |
| `s3/videos_bucket` | bucket de vídeos | `fiapx-infra` | `fiapx-video-api`, `fiapx-video-processor` |
| `sqs/video-uploaded/url`, `/arn` | fila de eventos do S3 | `fiapx-infra` | `fiapx-video-api` |
| `sqs/processing-commands/url`, `/arn` | fila de comandos do worker | `fiapx-infra` | `fiapx-video-api`, `fiapx-video-processor` |
| `sqs/saga-replies/url`, `/arn` | fila FIFO de respostas | `fiapx-infra` | `fiapx-video-api`, `fiapx-video-processor`, `fiapx-notification` |
| `sqs/<fila>-dlq/url` | DLQ de cada fila | `fiapx-infra` e `fiapx-notification` | alarmes, reprocessamento manual |
| `sqs/notification-commands/url`, `/arn` | fila de comandos de e-mail | `fiapx-notification` | `fiapx-video-api`, `fiapx-auth` |
| `dynamodb/notifications/table_name` | histórico de e-mails | `fiapx-notification` | `fiapx-notification` |
| `ses/from_address` | `nao-responda@hackfiapf5.click` | `fiapx-infra` | `fiapx-notification` |
| `ses/configuration_set` | configuration set do SES | `fiapx-infra` | `fiapx-notification` |
| `apigw/api_id`, `apigw/vpc_link_id` | API Gateway e VPC Link | `fiapx-infra` | `fiapx-auth` (rotas), `fiapx-video-api` (integração) |
| `alb/target_group_arn` | target group do ALB interno | `fiapx-infra` | `fiapx-video-api` (`TargetGroupBinding`) |
| `ecr/<repo>/url` | repositório de imagens | `fiapx-infra` | `fiapx-video-api`, `fiapx-video-processor` |
| `web/bucket`, `web/cloudfront_distribution_id` | hospedagem do front | `fiapx-infra` | `fiapx-web` |
| `web/url` | URL pública do front | `fiapx-infra` | `fiapx-auth` (link de redefinição), `fiapx-notification` (links dos e-mails) |

As chaves de rede, EKS, API Gateway, ALB, ECR e CloudFront existem só em `prod`. No ambiente local, o
init do LocalStack publica as demais (24 parâmetros).

## Segredos (Secrets Manager)

| Nome | Conteúdo | Quem lê |
|---|---|---|
| `fiapx/<env>/auth/jwt-private-key` | chave privada RSA do JWT (PEM) | Lambdas `login` e `password` |
| `fiapx/<env>/db/auth` | JSON `{engine, host, port, username, password, dbname}` | `fiapx-auth` |
| `fiapx/<env>/db/video` | mesmo formato | `fiapx-video-api` |

No ambiente local, a chave RSA é gerada a cada subida do LocalStack, e nenhuma chave fica versionada.
