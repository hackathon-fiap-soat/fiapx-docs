# ADR-007 — Amazon SQS como mensageria (Standard para comandos, FIFO para respostas, DLQ em todas)

- **Status:** Aceito
- **Data:** 2026-11-16
- **Decisores:** Diego Fenille, Eduardo Santos
- **Relacionados:** RFC-006 (mensageria), [ADR-006](ADR-006-upload-direto-s3-e-inicio-da-saga-pelo-evento.md), [ADR-008](ADR-008-saga-orquestrada-com-outbox-e-consumidores-idempotentes.md), [ADR-009](ADR-009-worker-laravel-no-eks-escalado-por-keda.md), [ADR-013](ADR-013-notificacao-sqs-lambda-ses-e-historico-no-dynamodb.md)

## Contexto

O RF2 exige que nenhuma requisição se perca em picos, e o RF1 exige processar vários vídeos ao mesmo tempo. O projeto base processa tudo de forma síncrona, sem fila.

A SAGA ([ADR-008](ADR-008-saga-orquestrada-com-outbox-e-consumidores-idempotentes.md)) troca comandos e respostas entre `video-api` (PHP), `video-processor` (PHP) e a Lambda de notificação (Node.js). O S3 precisa publicar o evento de upload em uma fila. O enunciado recomenda RabbitMQ ou Kafka; o time escolheu SQS, e a justificativa está na RFC-006.

## Decisão

Usamos **Amazon SQS** em toda a comunicação assíncrona, com **DLQ (`*-dlq`) em todas as filas**:

| Fila | Tipo | Produtor | Consumidor | Visibility | `maxReceiveCount` |
| --- | --- | --- | --- | --- | --- |
| `fiapx-<env>-video-uploaded` | Standard | S3 (`s3:ObjectCreated`) | `video-api` `saga-consumer` | 60 s | 5 |
| `fiapx-<env>-processing-commands` | Standard | `video-api` `outbox-relay` | `video-processor` | 300 s + heartbeat | 3 |
| `fiapx-<env>-saga-replies.fifo` | FIFO (`MessageGroupId = saga_id`) | `video-processor`, `notification` | `video-api` `saga-consumer` | 60 s | 3 |
| `fiapx-<env>-notification-commands` | Standard | `video-api` `outbox-relay` | Lambda `notification` | 60 s | 3 |

- **Comandos em filas Standard:** throughput alto e sem necessidade de ordem. A idempotência dos consumidores trata a entrega "pelo menos uma vez".
- **Respostas em fila FIFO agrupada por `saga_id`:** as respostas de uma mesma saga chegam na ordem em que foram enviadas (`ProcessingStarted` antes de `VideoProcessed`), e sagas diferentes são processadas em paralelo.
- **Dono das filas:** as três primeiras são criadas pelo `fiapx-infra` (módulo `messaging`). A `notification-commands` é criada pelo repositório `fiapx-notification`, que publica a URL em `/fiapx/<env>/sqs/notification-commands/url` ([ADR-001](ADR-001-polyrepo-e-integracao-via-ssm-parameter-store.md)).
- **Contratos em JSON puro e versionados**, sem jobs serializados do Laravel, porque PHP e Node.js leem as mesmas mensagens. Todas usam o envelope:

```json
{
  "message_id": "uuid-v7",
  "type": "ProcessVideo",
  "version": 1,
  "saga_id": "uuid-v7",
  "video_id": "uuid-v7",
  "correlation_id": "uuid-v7",
  "occurred_at": "2026-11-16T12:00:00Z",
  "payload": {}
}
```

- Tipos: `ProcessVideo`, `CleanupArtifacts`, `ProcessingStarted`, `VideoProcessed`, `VideoProcessingFailed`, `ArtifactsCleaned`, `SendNotification`, `NotificationSent` e `NotificationFailed`. Há um JSON Schema por mensagem em `fiapx-docs/contracts/`, validado nos *contract tests* de cada serviço.
- Mudança incompatível sobe a `version`, e os consumidores aceitam as duas versões durante a transição.
- **Alarmes:** `ApproximateNumberOfMessagesVisible > 0` em qualquer DLQ, no CloudWatch e integrado ao New Relic ([ADR-011](ADR-011-observabilidade-com-new-relic.md)).

## Alternativas consideradas

| Alternativa | Por que não |
| --- | --- |
| SNS + SQS (fan-out) | Não há mais de um consumidor por mensagem. Cada comando tem um destino único |
| RabbitMQ (Amazon MQ) | Broker com instância paga e gerenciada pelo time. Sem integração nativa com eventos do S3 e com o KEDA tão simples quanto a do SQS |
| Kafka (MSK) | Custo e complexidade altos para o volume do projeto. Ordem e retenção de log não são necessárias |
| Jobs de fila do Laravel entre serviços | O payload serializado do PHP não pode ser lido pela Lambda Node.js e acopla os serviços ao framework |
| Tudo em filas FIFO | Throughput menor e sem ganho para comandos, que já são idempotentes |

A comparação completa está na RFC-006.

## Consequências

### Positivas

- Serviço gerenciado, sem servidor para operar, com integração nativa com S3, Lambda (event source mapping) e KEDA (`aws-sqs-queue`).
- Mensagens duráveis: picos viram fila, não erro (RF2).
- A DLQ isola mensagens problemáticas sem travar a fila, e o alarme avisa o time.

### Negativas / riscos

- Entrega "pelo menos uma vez" nas filas Standard: mensagens podem ser duplicadas.
- A ordem é garantida só dentro de um `MessageGroupId` na FIFO.
- Mensagens limitadas a 256 KB.
- Os contratos ficam fora do código e podem divergir.

### Mitigações

- Consumidores idempotentes por `message_id` (`processed_messages`) e guardas de transição na saga ([ADR-008](ADR-008-saga-orquestrada-com-outbox-e-consumidores-idempotentes.md)).
- As mensagens levam só chaves do S3, nunca o arquivo.
- JSON Schema por mensagem e *contract tests* no CI de cada serviço.
