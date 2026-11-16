# Observabilidade

Como o FIAP X é observado no New Relic: instrumentação de cada camada, padrão de logs, eventos customizados da
SAGA, dashboard, alertas e integração com a AWS. Fonte: `Projeto-hackton.md` §10 e ADR-011 / RFC-010.

## Visão geral

```mermaid
flowchart LR
  subgraph EKS[Amazon EKS]
    API[video-api<br/>agente PHP]
    PROC[video-processor<br/>agente PHP]
    NRI[nri-bundle<br/>infra, eventos e logs do cluster]
  end
  subgraph LAMBDA[Lambdas Node.js 24]
    AUTH[fiapx-auth]
    NOTIF[fiapx-notification]
  end
  subgraph AWS[Serviços gerenciados]
    SQS[(SQS + DLQs)]
    AUR[(Aurora MySQL)]
    S3[(S3)]
    GW[API Gateway]
  end
  CW[CloudWatch Metric Streams] --> FH[Kinesis Data Firehose]
  SQS & AUR & S3 & GW & LAMBDA -. métricas .-> CW
  API & PROC -- APM, eventos customizados e logs --> NR[New Relic]
  NRI -- K8s*Sample e logs --> NR
  AUTH & NOTIF -- layer New Relic: APM e logs --> NR
  FH -- Metric --> NR
  NR --> DASH[Dashboard FIAP X]
  NR --> ALERT[Alertas]
```

Atributo comum para seguir um vídeo de ponta a ponta: `video_id`, junto com `saga_id` e `correlation_id`
(presentes no envelope de todas as mensagens, ver [`contracts/`](../contracts/README.md)).

## Instrumentação por camada

| Camada | Instrumentação | Onde é configurada | O que chega no New Relic |
|---|---|---|---|
| EKS | Helm `nri-bundle` (infraestrutura, kube-state-metrics, eventos do Kubernetes, logs dos pods) | `fiapx-infra/modules/eks-addons` | `K8sClusterSample`, `K8sNodeSample`, `K8sPodSample`, `K8sDeploymentSample`, `K8sHpaSample`, `InfrastructureEvent`, `Log` |
| video-api e video-processor | Agente New Relic PHP na imagem Docker; logs JSON (Monolog `JsonFormatter`) no stdout | Dockerfile e `config/logging.php` de cada repositório | `Transaction`, `TransactionError`, `Span`, eventos customizados, `Log` (logs in context) |
| Lambdas (auth e notification) | Layer New Relic para Node.js + logs JSON no stdout | `infra/` (Terraform) de cada repositório | `AwsLambdaInvocation`, `AwsLambdaInvocationError`, `Span`, `Log` |
| SQS, Aurora, S3, API Gateway, Lambda, SES, DynamoDB | Integração AWS ↔ New Relic por CloudWatch Metric Streams | `fiapx-infra` | `Metric` (`aws.sqs.*`, `aws.rds.*`, `aws.s3.*`, `aws.apigateway.*`, `aws.lambda.*`, `aws.ses.*`, `aws.dynamodb.*`) |

Nomes das aplicações no APM (`newrelic.appname` / `NEW_RELIC_APP_NAME`): `fiapx-video-api`,
`fiapx-video-processor`, `fiapx-auth` e `fiapx-notification`. A license key fica no Secrets Manager e é
injetada como variável de ambiente; nunca vai para o repositório.

Os processos de linha de comando do `video-api` (`outbox:relay`, `saga:consume`, `schedule:run`) e o
`processor:consume` também rodam com o agente PHP. Por serem processos longos (ou, no caso do CronJob,
curtos), cada mensagem processada é registrada como transação *background* (`newrelic_start_transaction` /
`newrelic_end_transaction`), com o nome do tipo da mensagem (ex.: `SagaConsumer/VideoProcessed`).

## Padrão de logs

Todos os serviços escrevem **uma linha JSON por evento no stdout**. O agente (PHP), o `nri-bundle` (pods) ou a
layer (Lambda) encaminham para o New Relic com `trace.id`, `span.id` e `entity.guid` (logs in context).

Formato (o mesmo do Monolog `JsonFormatter`, também seguido pelas Lambdas Node.js para que as consultas
sejam iguais em todos os serviços):

```json
{
  "datetime": "2026-11-16T12:00:47.123456+00:00",
  "level_name": "INFO",
  "channel": "fiapx-video-api",
  "message": "Saga concluída",
  "context": {
    "env": "prod",
    "correlation_id": "0192f1c4-7a2b-7c3d-8e4f-5a6b7c8d9e10",
    "video_id": "0192f1c4-7a2b-7c3d-8e4f-5a6b7c8d9e0f",
    "saga_id": "0192f1c4-7d00-7e4f-8a5b-6c7d8e9f0a1d",
    "user_id": "0192f1c4-6a00-7b00-8c00-1d2e3f4a5b6c",
    "message_id": "0192f1c4-8004-7a00-9b00-000000000004",
    "message_type": "VideoProcessed"
  },
  "extra": {}
}
```

| Campo | Obrigatório | Descrição |
|---|---|---|
| `datetime` | sempre | ISO-8601 com fuso |
| `level_name` | sempre | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `channel` | sempre | Nome do serviço (`fiapx-video-api`, `fiapx-video-processor`, `fiapx-auth`, `fiapx-notification`) |
| `message` | sempre | Texto curto e estável (sem valores variáveis), para agrupar |
| `context.env` | sempre | `local` ou `prod` |
| `context.correlation_id` | sempre que existir | Vem do envelope; nas rotas HTTP, do `requestId` do API Gateway |
| `context.video_id` | quando houver vídeo | Id do vídeo |
| `context.saga_id` | quando houver saga | Id da saga |
| `context.user_id` | quando houver usuário | `sub` do JWT / header `x-user-id` |
| `context.message_id`, `context.message_type` | nos consumidores e produtores de mensagens | Campos do envelope |
| `context.error_code`, `context.exception` | em erros | Código de negócio e classe/stack da exceção |

No Laravel, um *processor* do Monolog preenche `context` a partir de um contexto por requisição/mensagem
(Infrastructure), para que use cases e controllers não precisem repetir os campos.

**Nunca registrar:** senha, JWT, chave privada, URL pré-assinada completa (a assinatura dá acesso ao arquivo),
`fields` do POST pré-assinado e o e-mail completo do usuário (usar `user_id`; na notification, mascarar como
`m***@example.com`).

Consulta típica (todos os logs de um vídeo, em ordem):

```sql
SELECT datetime, channel, level_name, message, context.saga_id, context.message_type
FROM Log
WHERE context.video_id = '0192f1c4-7a2b-7c3d-8e4f-5a6b7c8d9e0f'
SINCE 1 day ago LIMIT MAX
```

## Eventos customizados

### `VideoSagaTransition` (video-api)

Registrado a cada mudança de estado da saga ou de status do vídeo, depois do commit da transação
(`newrelic_record_custom_event`, por um adapter na Infrastructure que escuta os eventos de domínio).

| Atributo | Tipo | Descrição |
|---|---|---|
| `video_id` | string | Id do vídeo |
| `saga_id` | string | Id da saga (vazio nas transições de vídeo sem saga, ver abaixo) |
| `correlation_id` | string | Do envelope |
| `user_id` | string | Dono do vídeo |
| `from_state` | string | Estado da saga antes (`NONE` na criação) |
| `to_state` | string | Estado da saga depois (`STARTED`, `UPLOAD_VALIDATED`, `QUOTA_RESERVED`, `PROCESSING_REQUESTED`, `PROCESSING`, `COMPLETED`, `NOTIFIED`, `COMPENSATING`, `COMPENSATED`) |
| `step` | string | Passo da saga (`ValidateUpload`, `ReserveQuota`, `ProcessVideo`, `CompleteVideo`, `NotifyUser`) ou compensação (`DeleteUploadedObject`, `ReleaseQuota`, `CleanupArtifacts`) |
| `duration_ms` | número | Tempo que a saga ficou em `from_state` |
| `video_status` | string | Status do vídeo depois da transição (`PENDING_UPLOAD` … `EXPIRED`) |
| `trigger` | string | O que causou a transição: tipo da mensagem recebida, `S3ObjectCreated` ou `Timeout` |
| `failure_reason` | string | Motivo da falha (`INVALID_UPLOAD`, `QUOTA_EXCEEDED`, `FFMPEG_ERROR`, `NO_FRAMES`, `DOWNLOAD_ERROR`, `UPLOAD_ERROR`, `TIMEOUT`), só nas falhas |

Transições do vídeo fora da saga (criação em `PENDING_UPLOAD` pelo `POST /api/videos` e expiração em
`EXPIRED`) também geram o evento, com `saga_id`, `from_state` e `to_state` vazios e `step` igual a
`RequestVideoUpload` ou `ExpirePendingUpload`. Assim o widget "Vídeos por status" cobre todos os status.

### `VideoProcessed` (video-processor)

Registrado quando o zip foi gravado no S3, antes de publicar a resposta `VideoProcessed`.

| Atributo | Tipo | Descrição |
|---|---|---|
| `video_id`, `saga_id`, `correlation_id` | string | Do envelope do `ProcessVideo` |
| `worker_id` | string | Nome do pod |
| `duration_ms` | número | Duração total (download + `ffmpeg` + zip + upload) |
| `ffmpeg_ms` | número | Só a extração dos frames |
| `frame_count` | número | Frames no zip |
| `video_size_bytes` | número | Tamanho do vídeo baixado |
| `zip_size_bytes` | número | Tamanho do zip |
| `reused` | booleano | `true` quando o zip já existia (worker idempotente) e não houve reprocessamento |

### `SagaTimeoutCheck` (video-api, apoio aos alertas)

O New Relic não consulta o Aurora, então "sagas presas" é medido pelo próprio `saga:check-timeouts`
(a cada minuto): antes de compensar, ele conta as sagas em `PROCESSING` com `deadline_at` vencido.

| Atributo | Tipo | Descrição |
|---|---|---|
| `overdue_count` | número | Sagas em `PROCESSING` com `deadline_at` vencido no início da execução |
| `compensated_count` | número | Sagas cuja compensação foi disparada nessa execução |

Se `overdue_count` continua acima de zero minuto após minuto, a compensação não está andando (relay parado,
fila travada ou erro no consumidor).

## Dashboard

Arquivo importável: [`newrelic-dashboard.json`](newrelic-dashboard.json) (formato de export do New Relic, duas
páginas). Todas as consultas estão com `accountIds: [0]`, um placeholder. Antes de importar, troque pelo id
da conta:

```bash
jq --argjson id 1234567 'walk(if type == "object" and has("accountIds") then .accountIds = [$id] else . end)' \
  07-observabilidade/newrelic-dashboard.json > /tmp/dashboard.json
```

Depois, no New Relic: **Dashboards → Import dashboard** e cole o conteúdo de `/tmp/dashboard.json`.
Os nomes das filas e do cluster assumem o ambiente `prod` (`fiapx-prod-*`).

## Consultas dos widgets

As consultas abaixo são as mesmas do JSON do dashboard.

### Página "Processamento"

**Vídeos por status (hoje)** (`viz.pie`)

```sql
SELECT count(*) AS 'Vídeos' FROM (SELECT latest(video_status) AS status FROM VideoSagaTransition WHERE video_id IS NOT NULL FACET video_id LIMIT MAX) FACET status SINCE today
```

**Taxa de falha (24 h)** (`viz.billboard`)

```sql
SELECT percentage(count(*), WHERE to_state = 'COMPENSATED') AS 'Falhas (%)' FROM VideoSagaTransition WHERE to_state IN ('COMPLETED', 'COMPENSATED') SINCE 1 day ago
```

**Throughput de uploads** (`viz.line`)

```sql
SELECT count(*) AS 'Envios solicitados' FROM Transaction WHERE appName = 'fiapx-video-api' AND request.method = 'POST' AND request.uri = '/api/videos' TIMESERIES 5 minutes SINCE 6 hours ago
SELECT count(*) AS 'Uploads recebidos (saga iniciada)' FROM VideoSagaTransition WHERE to_state = 'STARTED' TIMESERIES 5 minutes SINCE 6 hours ago
```

**Tempo de processamento p50/p95 (s)** (`viz.line`)

```sql
SELECT percentile(duration_ms / 1000, 50, 95) FROM VideoProcessed TIMESERIES 15 minutes SINCE 1 day ago
```

**Taxa de falha ao longo do tempo (%)** (`viz.line`)

```sql
SELECT percentage(count(*), WHERE to_state = 'COMPENSATED') AS 'Falhas (%)' FROM VideoSagaTransition WHERE to_state IN ('COMPLETED', 'COMPENSATED') TIMESERIES 15 minutes SINCE 1 day ago
```

**Motivos de falha (24 h)** (`viz.bar`)

```sql
SELECT count(*) AS 'Falhas' FROM VideoSagaTransition WHERE to_state = 'COMPENSATED' FACET failure_reason SINCE 1 day ago
```

**Sagas presas (PROCESSING com deadline vencido)** (`viz.billboard`)

```sql
SELECT latest(overdue_count) AS 'Sagas vencidas' FROM SagaTimeoutCheck SINCE 30 minutes ago
```

**Sagas vencidas ao longo do tempo** (`viz.line`)

```sql
SELECT max(overdue_count) AS 'Vencidas', sum(compensated_count) AS 'Compensadas por timeout' FROM SagaTimeoutCheck TIMESERIES 5 minutes SINCE 1 day ago
```

### Página "Filas, worker e API"

**Profundidade das filas** (`viz.line`)

```sql
SELECT max(aws.sqs.ApproximateNumberOfMessagesVisible) FROM Metric WHERE aws.sqs.QueueName LIKE 'fiapx-prod-%' AND aws.sqs.QueueName NOT LIKE '%-dlq%' FACET aws.sqs.QueueName TIMESERIES 5 minutes SINCE 6 hours ago
```

**Mensagens nas DLQs** (`viz.billboard`)

```sql
SELECT latest(aws.sqs.ApproximateNumberOfMessagesVisible) FROM Metric WHERE aws.sqs.QueueName LIKE 'fiapx-prod-%-dlq%' FACET aws.sqs.QueueName SINCE 30 minutes ago
```

**Réplicas do worker (KEDA) x fila processing-commands** (`viz.line`)

```sql
SELECT latest(podsAvailable) AS 'Pods disponíveis', latest(podsDesired) AS 'Pods desejados' FROM K8sDeploymentSample WHERE clusterName LIKE 'fiapx-prod%' AND deploymentName LIKE '%video-processor%' TIMESERIES 1 minute SINCE 6 hours ago
SELECT max(aws.sqs.ApproximateNumberOfMessagesVisible) AS 'Mensagens na processing-commands' FROM Metric WHERE aws.sqs.QueueName = 'fiapx-prod-processing-commands' TIMESERIES 1 minute SINCE 6 hours ago
```

**API Gateway — latência (ms)** (`viz.line`)

```sql
SELECT average(aws.apigateway.Latency) AS 'Latência média', max(aws.apigateway.Latency) AS 'Latência máxima', average(aws.apigateway.IntegrationLatency) AS 'Integração média' FROM Metric WHERE aws.apigateway.ApiId IS NOT NULL TIMESERIES 5 minutes SINCE 6 hours ago
```

**API Gateway — erros 4xx/5xx (%)** (`viz.line`)

```sql
SELECT sum(`aws.apigateway.4xx`) * 100 / sum(aws.apigateway.Count) AS '4xx (%)', sum(`aws.apigateway.5xx`) * 100 / sum(aws.apigateway.Count) AS '5xx (%)' FROM Metric WHERE aws.apigateway.ApiId IS NOT NULL TIMESERIES 5 minutes SINCE 6 hours ago
```

**video-api — latência p50/p95 (s)** (`viz.line`)

```sql
SELECT percentile(duration, 50, 95) FROM Transaction WHERE appName = 'fiapx-video-api' AND transactionType = 'Web' TIMESERIES 5 minutes SINCE 6 hours ago
```

**video-api — taxa de erro 5xx (%)** (`viz.line`)

```sql
SELECT percentage(count(*), WHERE http.statusCode >= 500) AS '5xx (%)' FROM Transaction WHERE appName = 'fiapx-video-api' AND transactionType = 'Web' TIMESERIES 5 minutes SINCE 6 hours ago
```

**Lambdas — invocações e erros** (`viz.table`)

```sql
SELECT sum(aws.lambda.Invocations) AS 'Invocações', sum(aws.lambda.Errors) AS 'Erros', average(aws.lambda.Duration) AS 'Duração média (ms)', sum(aws.lambda.Throttles) AS 'Throttles' FROM Metric WHERE aws.lambda.FunctionName LIKE 'fiapx-prod-%' FACET aws.lambda.FunctionName SINCE 1 day ago
```

## Alertas

Condições NRQL (New Relic Alerts), todas na política **FIAP X — prod**, com notificação por e-mail para o
time. Agregação por janela deslizante quando indicado.

| Alerta | Condição NRQL | Threshold (crítico) | Ação esperada |
|---|---|---|---|
| Mensagem em DLQ | `SELECT max(aws.sqs.ApproximateNumberOfMessagesVisible) FROM Metric WHERE aws.sqs.QueueName LIKE 'fiapx-prod-%-dlq%' FACET aws.sqs.QueueName` | `> 0` em pelo menos 1 minuto | Ler a mensagem, corrigir a causa e reprocessar (redrive) |
| Taxa de falha de processamento | `SELECT percentage(count(*), WHERE to_state = 'COMPENSATED') FROM VideoSagaTransition WHERE to_state IN ('COMPLETED', 'COMPENSATED')` | `> 10` (%) com janela de 15 minutos | Ver "Motivos de falha" e os logs do `fiapx-video-processor` |
| Fila `processing-commands` acumulada | `SELECT max(aws.sqs.ApproximateNumberOfMessagesVisible) FROM Metric WHERE aws.sqs.QueueName = 'fiapx-prod-processing-commands'` | `> 50` por 10 minutos | Conferir KEDA (`maxReplicaCount`), nós do EKS e erros no worker |
| Erros 5xx no API Gateway | `` SELECT sum(`aws.apigateway.5xx`) * 100 / sum(aws.apigateway.Count) FROM Metric WHERE aws.apigateway.ApiId IS NOT NULL `` | `> 2` (%) por 5 minutos | Ver Lambdas de auth, ALB e `video-api` |
| Erros 5xx no video-api | `SELECT percentage(count(*), WHERE http.statusCode >= 500) FROM Transaction WHERE appName = 'fiapx-video-api' AND transactionType = 'Web'` | `> 2` (%) por 5 minutos | Ver `TransactionError` e logs do `video-api` |
| Sagas vencidas | `SELECT max(overdue_count) FROM SagaTimeoutCheck` | `> 0` por 5 minutos | Conferir `outbox-relay`, `saga-consumer` e CronJob |

Recomendação complementar: ligar *loss of signal* (5 minutos) na condição "Sagas vencidas", para avisar se o
CronJob `schedule:run` parar de rodar.

As DLQs também têm alarmes no CloudWatch (`ApproximateNumberOfMessagesVisible > 0`, §7.1), criados pelo
Terraform. Eles chegam ao New Relic pela mesma integração e servem de redundância caso a condição NRQL
fique sem dados.

## Integração AWS (CloudWatch Metric Streams)

As métricas dos serviços gerenciados chegam ao New Relic por **CloudWatch Metric Streams**, criados pelo
Terraform no `fiapx-infra`:

1. Integração da conta AWS no New Relic (*AWS → Metric Streams*): role IAM que o New Relic assume para ler
   metadados e tags.
2. `aws_kinesis_firehose_delivery_stream` com destino HTTP no endpoint do New Relic (license key no Secrets
   Manager) e bucket S3 de backup para entregas com falha.
3. `aws_cloudwatch_metric_stream` em formato `opentelemetry0.7`, filtrando só os namespaces usados:
   `AWS/SQS`, `AWS/RDS`, `AWS/S3`, `AWS/ApiGateway`, `AWS/Lambda`, `AWS/SES`, `AWS/DynamoDB` e `AWS/Firehose`.

| Namespace | Métricas usadas | Onde |
|---|---|---|
| `AWS/SQS` | `ApproximateNumberOfMessagesVisible`, `ApproximateAgeOfOldestMessage`, `NumberOfMessagesSent` | Filas, DLQs e alertas |
| `AWS/RDS` | `ServerlessDatabaseCapacity`, `DatabaseConnections`, `CPUUtilization` | Capacidade do Aurora Serverless v2 |
| `AWS/S3` | `BucketSizeBytes`, `NumberOfObjects` (diárias) | Volume de vídeos e zips |
| `AWS/ApiGateway` | `Count`, `4xx`, `5xx`, `Latency`, `IntegrationLatency` | Latência e erros do gateway |
| `AWS/Lambda` | `Invocations`, `Errors`, `Duration`, `Throttles` | Auth e notification |
| `AWS/SES` | `Send`, `Delivery`, `Bounce`, `Complaint` | Envio de e-mails |

As métricas chegam como eventos `Metric` com o prefixo `aws.` e as dimensões como atributos (ex.:
`aws.sqs.QueueName`). As métricas do S3 por bucket são diárias; métricas de requisição do S3 não são
habilitadas, para não gerar custo.

## Como seguir um vídeo ponta a ponta

1. Pegue o `video_id` na tela "Meus vídeos" ou na resposta do `POST /api/videos`.
2. Transições da saga:
   `SELECT timestamp, from_state, to_state, step, trigger, duration_ms FROM VideoSagaTransition WHERE video_id = '<id>' SINCE 1 day ago`.
3. Processamento: `SELECT * FROM VideoProcessed WHERE video_id = '<id>' SINCE 1 day ago`.
4. Logs de todos os serviços: `SELECT * FROM Log WHERE context.video_id = '<id>' SINCE 1 day ago`.
