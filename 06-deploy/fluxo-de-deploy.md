# Fluxo de deploy

Cada repositório tem a própria pipeline no GitHub Actions. O `prod` roda na AWS Academy Learner Lab, que
não permite provedor OIDC nem roles próprias
([ADR-019](../04-adrs/ADR-019-deploy-na-aws-academy-learner-lab.md)): a autenticação na AWS usa as
credenciais temporárias da sessão do lab, guardadas em GitHub Secrets (`AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`) e passadas ao `aws-actions/configure-aws-credentials` com a
região `us-east-1`. Elas são atualizadas a cada sessão do lab
([procedimento](ambientes.md#sessão-do-lab-e-credenciais)).

## Princípios

- **Pull request obrigatório** para mudar a `main`. A aprovação é opcional (decisão do time): qualquer
  integrante, inclusive o autor, pode fazer o merge depois que os checks passarem.
- **Checks obrigatórios** em todo PR (proteção da `main` em todos os repositórios): lint, testes, cobertura ≥ 80% e
  Quality Gate do [SonarCloud](https://sonarcloud.io/organizations/hackathon-fiap-soat/projects). O scanner roda no CI
  depois dos testes (`sonar-project.properties` em cada repositório, Secret `SONAR_TOKEN`), com a action fixada pelo SHA.
- **Deploy só na `main`**, com o GitHub Environment `prod`.
- **Imagens imutáveis:** tag igual ao SHA do commit, scan com Trivy (falha em `CRITICAL`).
- **`terraform apply` só pelo GitHub Actions, sem exceção.** Apply local só no LocalStack. Não há bootstrap
  manual: o primeiro passo de todo job Terraform garante, de forma idempotente, o bucket do state
  `fiapx-tfstate-<account_id>` (versionado, SSE-S3, Block Public Access) e o passa no
  `terraform init -backend-config=bucket=...`; o lock é nativo do S3 (`use_lockfile`).
- **Segredos só em GitHub Secrets**, nunca em Variables: os repositórios são públicos e Variables não são
  mascaradas nos logs.
- **Integração por SSM:** cada repositório lê de `/fiapx/<env>/...` os recursos criados por outro; nenhum
  usa `terraform_remote_state`.

## Pipelines por tipo de repositório

| Repositório | Pull request | Merge na `main` |
|---|---|---|
| `fiapx-docs` | markdownlint, validação dos JSON Schemas e exemplos, lint do OpenAPI (Spectral), renderização dos diagramas Mermaid | GitHub Pages (opcional) |
| `fiapx-infra` | `fmt -check`, `validate`, `tflint`, `checkov`, `plan` comentado no PR | `apply` no environment `prod` |
| `fiapx-auth` e `fiapx-notification` | eslint, jest (cobertura ≥ 80%), Sonar, `terraform plan` | build do zip → `terraform apply` → (auth) invocação da Lambda `migrate`, que aplica as migrations dentro da VPC, porque o runner não alcança o Aurora privado → smoke test |
| `fiapx-web` | eslint, vitest (cobertura ≥ 80%), Sonar, build | build da imagem nginx com `VITE_API_BASE_URL=/api` → push no ECR `fiapx-web` → `terraform apply` do `infra/` (rota `$default` do HTTP API) → `kubectl apply -k` (Deployment, Service e `TargetGroupBinding`) → `rollout status` → smoke com Playwright na URL do API Gateway |
| `fiapx-video-api` | pint, phpstan (nível 6+), phpunit (cobertura ≥ 80%, com MySQL e LocalStack do `fiapx-infra/local`), behat (SAGA), Sonar, build + Trivy, kustomize + kubeconform, `terraform plan` do `infra/` | push no ECR → `terraform apply` do `infra/` (rotas) → `aws.env` do SSM e Secrets do banco e do app → manifests sem os Deployments → Job `migrate` concluído → Deployments → `rollout status` → smoke test |
| `fiapx-video-processor` | pint, phpstan, phpunit (inclui integração com `ffmpeg` real e um vídeo de 3 s), Sonar, build + Trivy | push no ECR → `kustomize edit set image` → `kubectl apply -k` → `rollout status` |

Os quatro tipos de pipeline, lado a lado:

```mermaid
flowchart TB
  subgraph EKS["Aplicações no EKS: fiapx-video-api e fiapx-video-processor"]
    direction LR
    E1["PR"] --> E2["pint, phpstan"] --> E3["phpunit, behat"] --> E4["SonarCloud"] --> E5["docker build<br/>+ Trivy"] --> E6["merge na main"] --> E7["push no ECR<br/>tag = SHA"] --> E8["Job migrate<br/>só video-api"] --> E9["kustomize edit set image<br/>kubectl apply -k"] --> E10["rollout status<br/>+ smoke test"]
  end
  subgraph LAMBDA["Lambdas com Terraform: fiapx-auth e fiapx-notification"]
    direction LR
    L1["PR"] --> L2["eslint"] --> L3["jest ≥ 80%"] --> L4["SonarCloud"] --> L5["terraform plan<br/>comentado"] --> L6["merge na main"] --> L7["build do zip"] --> L8["terraform apply<br/>env prod"] --> L9["smoke test"]
  end
  subgraph INFRA["Infraestrutura: fiapx-infra"]
    direction LR
    I1["PR"] --> I2["fmt -check<br/>validate"] --> I3["tflint + checkov"] --> I4["plan<br/>comentado"] --> I5["merge na main"] --> I6["apply<br/>env prod"] --> I7["parâmetros SSM"]
  end
  subgraph WEB["Front-end: fiapx-web"]
    direction LR
    W1["PR"] --> W2["eslint"] --> W3["vitest ≥ 80%"] --> W4["SonarCloud"] --> W5["npm run build"] --> W6["merge na main"] --> W7["docker build nginx<br/>VITE_API_BASE_URL=/api"] --> W8["push no ECR"] --> W9["terraform apply<br/>rota $default"] --> W10["kubectl apply -k<br/>rollout status"] --> W11["Playwright smoke<br/>URL do API Gateway"]
  end
  EKS ~~~ LAMBDA ~~~ INFRA ~~~ WEB
```

Nos PRs, a pipeline para no merge: só os checks rodam. O deploy começa no merge na `main`, com as
credenciais do lab dos GitHub Secrets.

Smoke tests: no `fiapx-auth`, cadastro e login de um usuário de teste; no `fiapx-notification`, um
`SendNotification` de teste para um e-mail do time e conferência do item `SENT` no DynamoDB.

## Ordem entre repositórios (primeira subida)

```mermaid
flowchart TD
  B["bucket do state<br/>fiapx-tfstate-account_id<br/>criado pelo workflow, idempotente"] --> I["fiapx-infra envs/prod<br/>VPC, EKS, Aurora, S3, SQS, ECR, API GW, ALB, SSM"]
  I --> SQL["create-databases.sql<br/>Job no cluster ou passo do pipeline"]
  SQL --> AUTH["fiapx-auth<br/>migrations + lambdas + rotas /api/auth + authorizer"]
  SQL --> API["fiapx-video-api<br/>migrate + deploy + TargetGroupBinding + rotas /api/videos"]
  AUTH --> API
  I --> PROC["fiapx-video-processor<br/>deploy + ScaledObject"]
  I --> NOTIF["fiapx-notification<br/>SQS + lambda + DynamoDB<br/>publica URL da fila no SSM"]
  NOTIF --> API
  NOTIF --> AUTH
  I --> WEB["fiapx-web<br/>imagem nginx + rota $default<br/>+ TargetGroupBinding"]
  API --> E2E["smoke test ponta a ponta<br/>register → login → upload → COMPLETED → download"]
  PROC --> E2E
  NOTIF --> E2E
  WEB --> E2E
```

Por que essa ordem:

1. O primeiro passo de cada job Terraform garante o bucket do state. Não há roles para criar: tudo usa a
   `LabRole` do lab.
2. O `fiapx-infra` publica no SSM tudo o que os outros repositórios precisam.
3. Os databases precisam existir antes das migrations do `fiapx-auth` e do `fiapx-video-api`.
4. O `fiapx-auth` publica e-mails de senha na fila `notification-commands`, criada pelo
   `fiapx-notification` (ADR-017).
5. O `fiapx-video-api` depende do authorizer (`fiapx-auth`) para as rotas `/api/videos` e da fila
   `notification-commands` (`fiapx-notification`) para publicar `SendNotification`.

Depois da primeira subida, cada repositório faz deploy de forma independente: todo merge na `main` faz
deploy do próprio serviço.

## Orquestração (subir e derrubar tudo)

Como o ambiente `prod` é destruído fora das demonstrações, a subida na ordem acima é feita por um
orquestrador no `fiapx-infra` ([ADR-018](../04-adrs/ADR-018-orquestracao-do-deploy-no-github-actions.md)):

| Workflow | Confirmação | O que faz |
|---|---|---|
| `deploy-all.yml` | `deploy-prod` (só no disparo manual) | `apply` da infra e `create-databases.sql`, depois chama o `deploy.yml` de cada repositório na ordem e roda o smoke test ponta a ponta. Input opcional `a_partir_de` para retomar uma subida interrompida. **Também roda sozinho**, a partir da notification, depois de todo `apply` com sucesso do `terraform.yml` na `main` (merge no `fiapx-infra`) |
| `destroy-all.yml` | `destroy-prod` | Chama o `destroy.yml` de cada repositório na ordem inversa e destrói a infra por último |

Na aba Actions eles aparecem como `Deploy-all · sobe o ambiente prod inteiro` e
`Destroy-all · derruba o ambiente prod inteiro`. Os jobs são numerados pela ordem:
`0 · Confirmar e definir o ponto de partida`, `1 · Infraestrutura (Terraform apply)`,
`2 · Notificação (Lambda, fila e tabela)`, `3 · Auth (Lambdas e rotas)`, `4 · Video API (EKS)`,
`4 · Processor (EKS + KEDA)` e `4 · Site (nginx no EKS)` em paralelo, e `5 · Smoke ponta a ponta`; no
`destroy-all`, a ordem inversa. O workflow chamado aparece como `<etapa> / Implantar` ou `<etapa> / Remover`.
O disparo automático depende do nome exibido do `terraform.yml`
(`Terraform · plan no PR e apply da infraestrutura na main`), que o `deploy-all.yml` escuta em
`on.workflow_run.workflows`: renomear um exige mudar o outro.

Cada repositório de serviço tem um `deploy.yml` com dois gatilhos, `push` na `main` (merge) e
`workflow_call` (orquestrador), para que o deploy seja o mesmo nos dois caminhos. Nos dois caminhos o job
usa as mesmas credenciais do lab (Secrets da organização); com a sessão vencida, o job falha com
`ExpiredToken` e basta atualizar os Secrets e reexecutar.

Um merge feito com o ambiente destruído gera um deploy que falha ao ler os parâmetros do SSM, com uma
mensagem dizendo para rodar o `deploy-all`.

No `deploy-all`, cada etapa só roda se a anterior terminou com sucesso, ou se foi pulada de propósito pelo
`a_partir_de`. Uma falha para a cadeia ali, e o smoke não roda.

O smoke confere o site (`/` e `/login` servem o `index.html` do SPA), `GET /api/health/ready` (banco e
SQS), cadastro, login, `GET /api/videos` autenticado, 401 sem token, um vídeo de 3 s do upload até
`COMPLETED` com o zip de 3 frames, e o e-mail `VIDEO_COMPLETED` registrado no DynamoDB (`SENT` exigido quando
o Secret `SMTP_FROM` existe; sem ele, só um aviso). Cada etapa nova acrescenta ao smoke o que ela entrega.

## Teste de deploy ao fim de cada implementação

Regra do time: **toda implementação termina testada na AWS**, não só no ambiente local. Ao concluir uma etapa
ou mudança relevante:

1. Iniciar a sessão do lab e atualizar os Secrets `AWS_*`.
2. Antes de mexer em infraestrutura nova, conferir as permissões com o simulador do IAM e as chaves KMS
   ([restrições conhecidas](ambientes.md#restrições-conhecidas-do-lab)).
3. Merge dos PRs (o `deploy.yml` de cada serviço roda no merge) ou `deploy-all` manual.
4. Smoke verde no `deploy-all` e verificação do que a etapa entregou.
5. `destroy-all` no fim, para não consumir o crédito do lab.

## Mudanças de contrato

Mudança compatível (campo novo opcional) entra direto. Mudança incompatível sobe uma nova `version` no
envelope, e os consumidores aceitam as duas versões durante a transição:

1. O consumidor passa a aceitar `version` 1 e 2 (deploy primeiro).
2. O produtor passa a emitir a `version` 2.
3. Depois que as filas esvaziarem da `version` 1, o consumidor remove o suporte antigo.

## Rollback

| Tipo | Como |
|---|---|
| Aplicação no EKS | `kubectl rollout undo deployment/<nome>` ou reverter o PR (a pipeline reimplanta a imagem anterior) |
| Lambdas | Reverter o PR: o apply volta o código e o alias para a versão anterior |
| Infraestrutura | Reverter o PR e deixar o `apply` do CI rodar |
| Migration | Migrations são aditivas (expand/contract): a versão anterior da aplicação continua funcionando com o schema novo |
