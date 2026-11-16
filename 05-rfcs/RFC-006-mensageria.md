# RFC-006 — Mensageria

- **Status:** Aprovada
- **Data:** 2026-11-16
- **Autores:** Diego Fenille, Eduardo Santos
- **ADR resultante:** ADR-007

## Resumo

Propomos o **Amazon SQS** como mensageria de todo o processamento: filas **Standard** para eventos e
comandos (`video-uploaded`, `processing-commands`, `notification-commands`), fila **FIFO** para as
respostas da SAGA (`saga-replies.fifo`, `MessageGroupId = saga_id`) e **DLQ em todas**. As mensagens são
**JSON puro com envelope versionado** (`message_id`, `type`, `version`, `saga_id`, `correlation_id`...),
validadas por JSON Schema em `fiapx-docs/contracts/`.

O enunciado recomenda RabbitMQ ou Kafka. **Divergimos de forma consciente**, e esta RFC mostra que o
requisito por trás da recomendação continua atendido.

## Motivação

O requisito que motiva a recomendação de RabbitMQ/Kafka é o **RF2: em picos, não perder nenhuma
requisição**, e o RF1 (processar vários vídeos em paralelo) com desacoplamento entre quem recebe e quem
processa. Precisamos de:

- buffer durável entre o upload e o processamento;
- reentrega quando um consumidor morre (worker no meio do `ffmpeg`);
- isolamento de mensagens venenosas (DLQ);
- ordem por saga nas respostas;
- integração nativa com S3 (evento de upload), Lambda (notificação) e KEDA (escala).

## Proposta

| Fila | Tipo | Produtor → consumidor | Visibility | DLQ (`maxReceiveCount`) |
| --- | --- | --- | --- | --- |
| `fiapx-<env>-video-uploaded` | Standard | S3 → `saga-consumer` | 60 s | 5 |
| `fiapx-<env>-processing-commands` | Standard | `outbox-relay` → `video-processor` | 300 s + heartbeat | 3 |
| `fiapx-<env>-saga-replies.fifo` | FIFO | processor e notification → `saga-consumer` | 60 s | 3 |
| `fiapx-<env>-notification-commands` | Standard | `outbox-relay` → Lambda notification | 60 s | 3 |

- Entrega "at least once" tratada por idempotência (`processed_messages`, chave determinística do zip,
  `attribute_not_exists` no DynamoDB).
- Contratos em JSON puro (não jobs serializados do Laravel), porque PHP e Node.js leem as mesmas mensagens.
- Alarme `ApproximateNumberOfMessagesVisible > 0` em qualquer DLQ, integrado ao New Relic.
- Local: SQS no LocalStack.

### Como o requisito do enunciado continua atendido

| Necessidade (RF1/RF2) | RabbitMQ/Kafka | Como o SQS atende |
| --- | --- | --- |
| Durabilidade em pico | Disco do broker, replicação configurada pelo time | Armazenamento redundante em várias AZs, gerenciado; sem limite prático de mensagens enfileiradas |
| Não perder mensagem se o consumidor cair | ack manual / commit de offset | Visibility timeout + `DeleteMessage` só após o sucesso + heartbeat |
| Mensagem venenosa | Dead letter exchange / tópico de erro | Redrive policy com DLQ em todas as filas |
| Ordem | Fila única / partição por chave | FIFO com `MessageGroupId = saga_id` |
| Escala de consumidores | Consumidores no mesmo grupo | KEDA `aws-sqs-queue` e event source mapping da Lambda |

## Alternativas

| Critério | SQS (proposta) | SNS + SQS (fan-out) | RabbitMQ (Amazon MQ) | Kafka (Amazon MSK) |
| --- | --- | --- | --- | --- |
| Aderência à recomendação do enunciado | Diverge, atende o requisito | Diverge, atende o requisito | **Recomendado** | **Recomendado** |
| Integração com S3, Lambda e KEDA | Nativa | Nativa | S3 não publica direto; Lambda tem trigger | S3 não publica direto; Lambda tem trigger |
| Complexidade operacional | Muito baixa (serverless) | Baixa | Média (broker, versões, usuários) | Alta (brokers, partições, retenção) |
| Custo aproximado em baixo volume | Quase zero (por requisição) | Quase zero | Fixo por broker ligado 24 h | Alto: cluster mínimo com vários brokers |
| Escalabilidade | Automática | Automática | Vertical / cluster | Alta, com planejamento de partições |
| Necessidade de fan-out ou replay | Não há (comandos ponto a ponto) | Atende fan-out que não precisamos | Exchanges | Replay por offset que não precisamos |
| Rede | Endpoint de VPC | Endpoint de VPC | Broker dentro da VPC | Cluster dentro da VPC |
| Lock-in | Médio (isolado nas portas `CommandBus`/`ReplyPublisher`) | Médio | Baixo (AMQP) | Baixo (protocolo Kafka) |
| Curva de aprendizado do time | Baixa | Baixa | Média | Alta |

## Riscos

- **Divergência da stack recomendada** questionada na avaliação. Mitigação: esta RFC, a ADR-007 e a
  tabela acima explicam a equivalência; o vídeo de entrega mostra a fila absorvendo o pico.
- **Entrega duplicada** nas filas Standard. Mitigação: consumidores idempotentes e testes BDD de
  mensagem duplicada.
- **Limite de tamanho por mensagem do SQS.** Mitigação: mensagens levam só chaves do S3, nunca o arquivo.
- **Vazão da FIFO** (300 mensagens/s por API sem batching). Muito acima do volume esperado de respostas.
- **Lock-in de AWS.** Mitigação: adapters de mensageria trocáveis por RabbitMQ sem mudar o domínio.

## Decisão

Aprovada: Amazon SQS como mensageria, com filas Standard para eventos e comandos, FIFO para as respostas
da SAGA e DLQ em todas, divergindo conscientemente de RabbitMQ/Kafka sem perder o atendimento a RF1 e
RF2. A decisão é registrada na **ADR-007**.
