# Contratos de mensagens

Contratos (JSON Schema draft 2020-12) de todas as mensagens trocadas pelos serviços do FIAP X via Amazon SQS.
São a fonte da verdade para os *contract tests* de cada serviço (`Projeto-hackton.md` §7).

- As mensagens são **JSON puro e versionado**. Nunca trafegam jobs serializados do Laravel entre serviços.
- Toda mensagem nossa usa o [envelope padrão](envelope.schema.json) (§7.2). O conteúdo específico fica em `payload`.
- O evento do S3 (`s3:ObjectCreated`) não usa o envelope: é um formato da AWS, descrito em
  [`s3-object-created.schema.json`](s3-object-created.schema.json) só com os campos que o `saga-consumer` lê.
- Ao configurar a notificação do bucket, o S3 envia um `s3:TestEvent` (sem `Records`) para a fila
  `video-uploaded`. O `saga-consumer` reconhece essa mensagem, registra em log e a apaga, sem tratá-la como
  erro.

## Envelope

| Campo | Tipo | Descrição |
|---|---|---|
| `message_id` | UUID (v7) | Id único da mensagem. Chave de idempotência (`processed_messages` e DynamoDB) |
| `type` | string | Tipo da mensagem (tabela abaixo) |
| `version` | inteiro | Versão do contrato (hoje `1`) |
| `saga_id` | UUID | Id da saga. É o `MessageGroupId` na fila `saga-replies.fifo` |
| `video_id` | UUID | Id do vídeo |
| `correlation_id` | UUID | Propagado em logs e eventos do New Relic |
| `occurred_at` | date-time | Instante do fato ou do comando, em UTC |
| `payload` | objeto | Conteúdo do tipo |

Nenhum campo extra é aceito no envelope nem no `payload` (`additionalProperties: false`). Essa rigidez vale
para o produtor; o consumidor ignora campos desconhecidos (ver [Versionamento](#versionamento)).

## Filas, mensagens, produtores e consumidores

| Fila | Mensagens | Produtor | Consumidor |
|---|---|---|---|
| `fiapx-<env>-video-uploaded` | evento S3 `ObjectCreated` ([schema](s3-object-created.schema.json)) | Amazon S3 (prefixo `uploads/`) | `video-api` (`saga-consumer`) |
| `fiapx-<env>-processing-commands` | [`ProcessVideo`](process-video.v1.schema.json), [`CleanupArtifacts`](cleanup-artifacts.v1.schema.json) | `video-api` (`outbox-relay`) | `video-processor` |
| `fiapx-<env>-saga-replies.fifo` | [`ProcessingStarted`](processing-started.v1.schema.json), [`VideoProcessed`](video-processed.v1.schema.json), [`VideoProcessingFailed`](video-processing-failed.v1.schema.json), [`ArtifactsCleaned`](artifacts-cleaned.v1.schema.json) | `video-processor` | `video-api` (`saga-consumer`) |
| `fiapx-<env>-saga-replies.fifo` | [`NotificationSent`](notification-sent.v1.schema.json), [`NotificationFailed`](notification-failed.v1.schema.json) | `fiapx-notification` (Lambda) | `video-api` (`saga-consumer`) |
| `fiapx-<env>-notification-commands` | [`SendNotification`](send-notification.v1.schema.json) | `video-api` (`outbox-relay`, templates de vídeo) e `fiapx-auth` (Lambda `password`, templates de senha) | `fiapx-notification` (Lambda) |

Cada fila tem DLQ própria (`*-dlq`). Exemplos válidos de cada mensagem estão em [`examples/`](examples/).

## Convenção de chaves no S3

| Objeto | Chave |
|---|---|
| Vídeo enviado | `uploads/{video_id}.{ext}` (ex.: `uploads/0192f1c4-7a2b-7c3d-8e4f-5a6b7c8d9e0f.mp4`) |
| Prefixo de saída | `results/{video_id}/` |
| Pacote de frames | `results/{video_id}/frames.zip` |

O `ProcessVideo` só aceita as extensões permitidas (mp4, avi, mov, mkv, wmv, flv, webm). O evento do S3 aceita
qualquer chave sob `uploads/`, porque quem rejeita um upload inválido é o passo `ValidateUpload` da SAGA.
A chave chega codificada como URL no evento do S3 e deve ser decodificada antes do uso.

O S3 também envia um `s3:TestEvent` (sem `Records`) quando a notificação é configurada. O `saga-consumer`
deve descartá-lo sem erro.

## Versionamento

- O número da versão fica no campo `version` do envelope e no nome do arquivo (`<mensagem>.v<versão>.schema.json`).
- **Produtor estrito, consumidor tolerante.** Os schemas são estritos (`additionalProperties: false`) e são
  usados nos testes de contrato do **produtor**: ele só emite exatamente o que está no contrato. O
  **consumidor** valida os campos que usa e ignora campos que não conhece.
- Por isso, **campo opcional novo** é mudança compatível: o schema da mesma versão é atualizado, primeiro
  publicado no `fiapx-docs` e depois adotado pelo produtor.
- Mudança **incompatível** (campo removido, renomeado, com tipo diferente ou que passa a ser obrigatório) gera
  uma **nova versão**, em um novo arquivo (por exemplo, `process-video.v2.schema.json`).
- Durante a transição, os consumidores aceitam **as duas versões**. O produtor só passa a emitir a nova versão
  depois que todos os consumidores foram implantados com suporte a ela. A versão antiga é removida em um PR
  posterior.
- A versão `1` é a única existente hoje.

## Como validar localmente

O `ajv-cli` precisa do pacote `ajv-formats` instalado ao lado dele (por causa dos formatos `uuid`, `date-time`
e `email`), por isso o comando usa `-p` duas vezes:

```bash
npx -y -p ajv-cli@5 -p ajv-formats@3 ajv validate --spec=draft2020 --strict=true -c ajv-formats \
  -s contracts/process-video.v1.schema.json \
  -r contracts/envelope.schema.json \
  -d contracts/examples/process-video.v1.json
```

Validar todos os exemplos de uma vez (a partir da raiz do repositório):

```bash
for s in contracts/*.v1.schema.json; do
  n=$(basename "$s" .schema.json)
  npx -y -p ajv-cli@5 -p ajv-formats@3 ajv validate --spec=draft2020 --strict=true -c ajv-formats \
    -s "$s" -r contracts/envelope.schema.json -d "contracts/examples/$n.json"
done
npx -y -p ajv-cli@5 -p ajv-formats@3 ajv validate --spec=draft2020 --strict=true -c ajv-formats \
  -s contracts/s3-object-created.schema.json -d contracts/examples/s3-object-created.json
```

Os schemas referenciam o envelope por `$ref` relativo (`envelope.schema.json`), resolvido pelo `$id`
`https://github.com/hackathon-fiap-soat/fiapx-docs/contracts/`. Nos testes dos serviços, carregue o envelope
e o schema da mensagem no mesmo validador (Ajv no Node.js; `opis/json-schema` ou equivalente no PHP).

## Mensagens fora da saga

O `SendNotification` com os templates `PASSWORD_RESET` e `PASSWORD_CHANGED` é emitido pelo `fiapx-auth`
e não pertence a nenhuma saga: `saga_id` e `video_id` vão como `null`, e o `fiapx-notification` não
publica `NotificationSent`/`NotificationFailed` na `saga-replies.fifo` nesse caso. O envelope só aceita
esses campos nulos em `SendNotification`. O `action_url` do `PASSWORD_RESET` contém o token de
redefinição e nunca é gravado em log nem no DynamoDB (ver ADR-017).

Exemplos extras de uma mesma mensagem seguem o padrão `examples/<nome>--<variante>.json`, por exemplo
[`send-notification.v1--password-reset.json`](examples/send-notification.v1--password-reset.json).
