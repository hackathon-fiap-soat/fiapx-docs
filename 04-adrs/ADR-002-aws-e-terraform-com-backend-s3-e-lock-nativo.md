# ADR-002 — AWS como cloud e Terraform como IaC, com backend S3 e lock nativo

- **Status:** Aceito
- **Data:** 2026-11-16
- **Decisores:** Diego Fenille, Eduardo Santos
- **Relacionados:** RFC-001 (escolha da cloud e da IaC), [ADR-001](ADR-001-polyrepo-e-integracao-via-ssm-parameter-store.md), [ADR-012](ADR-012-ci-cd-com-github-actions-oidc-e-ordem-de-deploy.md), [ADR-016](ADR-016-terraform-apply-somente-via-github-actions.md)

## Contexto

O enunciado pede persistência, arquitetura escalável e um script de criação do banco de dados e dos demais recursos. O projeto base roda em uma única máquina e usa o disco local como "banco de dados".

A solução precisa de serviços gerenciados de fila, armazenamento de objetos, banco relacional, Kubernetes, funções serverless, e-mail transacional e CDN. Toda a infraestrutura precisa ser reproduzível, revisável em PR e destruível fora das demonstrações para controlar custo.

A escolha de cloud e IaC é uma decisão fechada pelo time (`Projeto-hackton.md` §3). Como vários repositórios e o CI vão aplicar Terraform ([ADR-001](ADR-001-polyrepo-e-integracao-via-ssm-parameter-store.md)), o state precisa ficar remoto e com lock.

## Decisão

- **Cloud:** AWS, região padrão `us-east-1`, configurável por variável.
- **IaC:** Terraform **≥ 1.10** em todos os repositórios que criam recursos (`fiapx-infra`, e o `infra/` de `fiapx-auth` e `fiapx-notification`).
- **Backend remoto:** bucket S3 versionado e criptografado, com **lock nativo do S3** (`use_lockfile = true`). Não usamos tabela DynamoDB de lock.
- **Bootstrap:** `fiapx-infra/bootstrap/` roda uma única vez, com state local. Ele cria o bucket do tfstate e as roles OIDC do GitHub de cada repositório ([ADR-012](ADR-012-ci-cd-com-github-actions-oidc-e-ordem-de-deploy.md)).
- **Organização do `fiapx-infra`:** módulos `network`, `eks`, `eks-addons`, `aurora`, `storage`, `messaging`, `ses`, `ecr`, `edge`, `web-hosting` e `ssm-outputs`, compostos em `envs/prod/`.
- **Script de criação do banco** (entregável): `fiapx-infra/sql/create-databases.sql` cria `fiapx_auth`, `fiapx_video` e os usuários com GRANT mínimo ([ADR-005](ADR-005-aurora-mysql-serverless-v2-um-database-por-servico.md)).
- **Ambiente local:** `fiapx-infra/local/docker-compose.yml` com `mysql:8.0`, LocalStack (S3, SQS, SES, SSM, Secrets Manager) e Mailpit.
- **Proteções:** `prevent_destroy` no Aurora, no bucket de vídeos e na tabela DynamoDB. Só o workflow `destroy-all.yml` desliga essas proteções, por variável explícita ([ADR-016](ADR-016-terraform-apply-somente-via-github-actions.md)).

Exemplo do backend:

```hcl
terraform {
  required_version = ">= 1.10"

  backend "s3" {
    bucket       = "<bucket-do-tfstate>"
    key          = "fiapx-infra/prod/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
```

O nome do bucket e as chaves de cada repositório são definidos no bootstrap. O exemplo acima é ilustrativo.

## Alternativas consideradas

| Alternativa | Por que não |
| --- | --- |
| GCP | Tem equivalentes (Pub/Sub, GKE, Cloud SQL), mas a solução foi desenhada sobre serviços AWS (SQS, SES, Lambda Authorizer, Aurora Serverless v2) |
| Azure | Mesmo motivo: não traz vantagem para os serviços que a arquitetura usa |
| CloudFormation / CDK | Restrito à AWS, sintaxe mais verbosa (CloudFormation) ou mais código imperativo (CDK). Terraform é multi-provider e tem o `plan` legível para revisão em PR |
| Backend S3 com lock em DynamoDB | O lock nativo do S3 (`use_lockfile`, Terraform ≥ 1.10) faz o mesmo sem uma tabela extra |
| State local versionado no Git | Perde o lock, arrisca vazar dados sensíveis do state e não funciona com o CI |

A comparação completa está na RFC-001.

## Consequências

### Positivas

- Toda a infraestrutura é código revisado em PR, com `plan` comentado ([ADR-012](ADR-012-ci-cd-com-github-actions-oidc-e-ordem-de-deploy.md)).
- O lock nativo impede dois `apply` simultâneos no mesmo state (CI e um integrante, por exemplo).
- O state versionado no S3 permite recuperar uma versão anterior.
- `terraform destroy` desliga o ambiente fora das demonstrações.

### Negativas / riscos

- EKS (cerca de US$ 73/mês só o control plane), NAT Gateway e Aurora são os itens mais caros.
- O bootstrap é manual e usa state local: se esse state se perder, os recursos do bootstrap precisam ser importados.
- Terraform ≥ 1.10 é obrigatório em todas as máquinas e no CI. Versões antigas não entendem `use_lockfile`.
- Alguns serviços (EKS, SES real) não podem ser testados no LocalStack.

### Mitigações

- O procedimento de `terraform destroy` e os custos ficam documentados em `06-deploy/ambientes.md`.
- O bootstrap é pequeno (bucket e roles), idempotente e documentado no README do `fiapx-infra`.
- `required_version = ">= 1.10"` em todos os módulos raiz. O CI fixa a versão do Terraform no setup.
- Apply local na AWS só para o que o LocalStack não cobre, seguindo [ADR-016](ADR-016-terraform-apply-somente-via-github-actions.md).
