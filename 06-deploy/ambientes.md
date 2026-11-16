# Ambientes

| Ambiente | Onde | Para quê |
|---|---|---|
| `local` | Máquina de cada integrante, com `docker compose` | Desenvolvimento, testes de integração e testes do Terraform no LocalStack |
| `prod` | Conta AWS do time, região `us-east-1` | Demonstração, teste de carga e gravação do vídeo |

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
| LocalStack | `localstack/localstack:4.14.0` (S3, SQS, SES, SSM, Secrets Manager, DynamoDB, Lambda, API Gateway, IAM) | Serviços AWS | `http://localhost:4566` |
| Mailpit | `axllent/mailpit:v1.33.1` | Caixa de entrada (o `fiapx-notification` usa `EMAIL_DRIVER=smtp`) | UI `http://localhost:8025`, SMTP `localhost:1025` |

O LocalStack está fixado na `4.14.0`, a última versão Community que roda sem `LOCALSTACK_AUTH_TOKEN`
(as versões `2026.x` exigem conta). Ele não guarda estado: os recursos são recriados a cada subida.

Os scripts de `fiapx-infra/local/init/` rodam o mesmo `sql/create-databases.sql` da AWS e criam o bucket,
as filas e DLQs, a notificação S3 → SQS, a tabela de notificações, os segredos e os
[parâmetros SSM](parametros-ssm.md) com os mesmos nomes de produção (`/fiapx/local/...`). Assim o código
é o mesmo nos dois ambientes; só muda o endpoint da AWS (`AWS_ENDPOINT_URL=http://localhost:4566`).

O EKS não é simulado localmente: o `video-api` e o `video-processor` rodam como containers no compose
(ou direto com `php artisan`), e o KEDA só é exercitado em `prod`.

Terraform local: `tflocal` com state em `.terraform-local/` (no `.gitignore`).

## Produção (AWS)

| Recurso | Configuração |
|---|---|
| Região | `us-east-1` (configurável) |
| Rede | VPC em 2 AZs, 1 NAT Gateway |
| EKS | 1 managed node group (instâncias spot quando possível), add-ons: AWS Load Balancer Controller, metrics-server, KEDA, New Relic `nri-bundle` |
| Aurora | MySQL Serverless v2, de 0,5 a 4 ACU |
| Prefixo dos recursos | `fiapx-prod-*` |
| Parâmetros | `/fiapx/prod/...` no SSM |

## Custos

Os itens mais caros ficam ligados o tempo todo enquanto o ambiente existir:

| Item | Custo aproximado |
|---|---|
| EKS (control plane) | ~US$ 73/mês |
| NAT Gateway | ~US$ 33/mês + tráfego |
| Aurora Serverless v2 (0,5 ACU mínimo) | ~US$ 45/mês |
| Nós do EKS | conforme tipo e quantidade (spot reduz bastante) |
| Domínio `hackfiapf5.click` + hosted zone | ~US$ 3–15/ano + US$ 0,50/mês |
| SQS, S3, Lambda, DynamoDB, SES, CloudFront | centavos no volume do hackathon |

Valores aproximados, para orientar a decisão de manter o ambiente desligado fora das demonstrações.

## Desligar e religar

Para manter o custo baixo, o ambiente `prod` é destruído fora das demonstrações:

1. Rodar o workflow manual `destroy.yml` no `fiapx-infra`, digitando a confirmação `destroy-prod`.
2. O workflow desliga o `prevent_destroy` (Aurora, bucket de vídeos e tabela DynamoDB) por variável
   explícita e roda `terraform destroy` na ordem inversa da subida (aplicações, Lambdas e por fim a
   infraestrutura).
3. Ficam de pé só o bucket do state, as roles OIDC (`bootstrap`), o domínio registrado e a hosted zone.

Para religar, basta seguir a [ordem de deploy](fluxo-de-deploy.md#ordem-entre-repositórios-primeira-subida)
a partir do `fiapx-infra`, disparando os workflows de cada repositório.
