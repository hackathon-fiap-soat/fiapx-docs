# RFC-003 — Estratégia da SAGA

- **Status:** Aprovada
- **Data:** 2026-11-16
- **Autores:** Diego Fenille, Eduardo Santos
- **ADR resultante:** ADR-008

## Resumo

Propomos uma **SAGA orquestrada pelo `fiapx-video-api`** (Laravel 13), com o agregado `ProcessingSaga`
persistido em `fiapx_video.processing_sagas`, comandos emitidos por **transactional outbox** e respostas
recebidas pela fila FIFO `saga-replies.fifo`. Todos os consumidores são **idempotentes** e o
comportamento da SAGA é coberto por **testes BDD** (Behat).

## Motivação

O processamento de um vídeo envolve passos locais (`ValidateUpload`, `ReserveQuota`, `CompleteVideo`) e
remotos (`ProcessVideo` no `video-processor`, `NotifyUser` no `fiapx-notification`). Como não existe
transação distribuída entre Aurora, S3, SQS e SES, precisamos de:

- estado explícito do processamento para a listagem (RF4);
- compensações quando um passo falha (apagar artefatos parciais, liberar a cota);
- notificação garantida do usuário na falha (RF5);
- tolerância a mensagens duplicadas, fora de ordem e a workers que morrem no meio (RF2).

## Proposta

- **Passos:** `ValidateUpload` → `ReserveQuota` → `ProcessVideo` → `CompleteVideo` (ponto sem retorno)
  → `NotifyUser`. Compensações: `DeleteUploadedObject`, `ReleaseQuota` e `CleanupArtifacts`, em ordem
  inversa.
- **Estados:** `STARTED → UPLOAD_VALIDATED → QUOTA_RESERVED → PROCESSING_REQUESTED → PROCESSING →
  COMPLETED → NOTIFIED`; na falha, `COMPENSATING → COMPENSATED (FAILED) → NOTIFIED`.
- **Início:** o evento `s3:ObjectCreated` na fila `video-uploaded` (ADR-006).
- **Transactional outbox:** a mudança de estado da saga e o comando (`ProcessVideo`, `CleanupArtifacts`,
  `SendNotification`) são gravados em `outbox_messages` na **mesma transação**. O `outbox-relay` publica
  com `SELECT ... FOR UPDATE SKIP LOCKED` e marca `published_at`.
- **Idempotência:** cada envelope tem `message_id` (UUID v7). O consumidor grava em `processed_messages`
  na mesma transação do efeito; repetição vira no-op. O worker é idempotente pela chave determinística
  `results/{video_id}/frames.zip`.
- **Guardas de transição e lock otimista** (`version`): transições inválidas, como `VideoProcessed` em
  saga `COMPENSATING`, são descartadas com log de warning, sem ir para a DLQ.
- **Ordem:** `saga-replies.fifo` com `MessageGroupId = saga_id`.
- **Timeout:** `saga:check-timeouts` roda a cada minuto e compensa sagas `PROCESSING_REQUESTED` ou `PROCESSING` com `deadline_at`
  vencido (padrão 30 min).
- **BDD obrigatório:** sucesso; falha no ffmpeg com compensação; timeout; cota excedida; upload
  inválido; mensagem duplicada; resposta fora de ordem.

## Alternativas

| Critério | Orquestrada no Laravel (proposta) | AWS Step Functions | Coreografia SNS/SQS |
| --- | --- | --- | --- |
| Onde fica o estado | `processing_sagas` no Aurora, junto do `Video` | Execução da state machine (fora do banco do serviço) | Espalhado entre os serviços |
| Visibilidade do fluxo | Alta: `history` JSON + evento `VideoSagaTransition` no New Relic | Alta: console visual | Baixa: depende de rastreio distribuído |
| Testabilidade | Alta: agregado em PHP puro, unit + Behat, sem AWS | Média: precisa de Step Functions Local ou da AWS | Baixa: cenários exigem todos os serviços |
| Consistência entre estado e mensagem | Outbox na mesma transação do MySQL | Exige sincronizar a execução com o banco (dual write) | Cada serviço precisa de outbox próprio |
| Compensações e timeout | Código de domínio + comando agendado | Nativos (`Catch`, `TimeoutSeconds`) | Difícil: ninguém "dono" do timeout |
| Acoplamento | Orquestrador conhece os participantes | Mesmo acoplamento, em ASL/JSON | Baixo, mas regras implícitas |
| Custo aproximado | Incluso nos pods existentes | Por transição de estado (baixo neste volume) | SNS + SQS (baixo) |
| Lock-in | Baixo (SQS atrás de portas) | Alto (ASL é exclusivo da AWS) | Médio |
| Curva de aprendizado do time | Baixa: a Fase 4 já teve uma saga (`PaymentSaga`) em Laravel | Média | Média |
| Aderência ao enunciado e ao DDD | Alta: regra de negócio no domínio | Média: regra fora do código de domínio | Média |

## Riscos

- **Orquestrador como ponto central de falha.** Mitigação: estado durável no Aurora, `saga-consumer`
  escalado por KEDA (1–5) e mensagens retidas no SQS enquanto ele estiver fora.
- **Outbox acumulando** se o relay cair. Mitigação: alerta de pendências antigas e 1–2 réplicas do relay
  com `SKIP LOCKED`.
- **Crescimento de `processed_messages` e `outbox_messages`.** Mitigação: limpeza periódica de registros
  publicados ou antigos (definir na implementação).
- **Corrida entre timeout e resposta tardia.** Mitigação: lock otimista e guardas de transição; o
  cenário "resposta fora de ordem" é coberto pelo BDD.
- **Complexidade maior que um fluxo síncrono.** Mitigação: documentação em `03-arquitetura/saga.md` e
  testes BDD como especificação executável.

## Decisão

Aprovada: SAGA orquestrada no `fiapx-video-api`, com estado no Aurora, transactional outbox,
consumidores idempotentes, guardas de transição, timeout agendado e BDD obrigatório. A decisão é
registrada na **ADR-008**.
