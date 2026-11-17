# ADR-011 — Observabilidade com New Relic

- **Status:** Aceito, parcialmente substituído por [ADR-019](ADR-019-deploy-na-aws-academy-learner-lab.md); dashboard e alertas como código pelo [ADR-021](ADR-021-observabilidade-como-codigo-no-new-relic.md)
- **Data:** 2026-11-16
- **Decisores:** Diego Fenille, Eduardo Santos
- **Relacionados:** RFC-010 (observabilidade), [ADR-007](ADR-007-amazon-sqs-como-mensageria.md), [ADR-008](ADR-008-saga-orquestrada-com-outbox-e-consumidores-idempotentes.md), [ADR-009](ADR-009-worker-laravel-no-eks-escalado-por-keda.md)

> **Atualização ([ADR-019](ADR-019-deploy-na-aws-academy-learner-lab.md)):** sem CloudWatch Metric Streams nem integração da conta AWS no New Relic (o lab não cria as roles). O New Relic fica com APM, Kubernetes (`nri-bundle`), logs e Lambdas (extensão com a license key). As métricas de SQS, DLQs, Aurora e API Gateway ficam no CloudWatch, com alarmes num tópico SNS com e-mail do time ([observabilidade.md](../07-observabilidade/observabilidade.md)).

## Contexto

A solução é distribuída: um vídeo passa pelo API Gateway, Lambdas, pods do EKS, três filas SQS, S3, Aurora e SES. Quando algo falha, é preciso seguir o caminho de um vídeo específico entre os serviços, saber se há mensagens paradas em DLQ, se o KEDA está escalando e se existem sagas presas.

O enunciado recomenda Prometheus + Grafana (ou ELK). Manter essas ferramentas exigiria operar Prometheus, Grafana, armazenamento de métricas e coleta de logs dentro do próprio cluster, além de instrumentar as Lambdas separadamente. A escolha do time é New Relic, e a justificativa está na RFC-010.

## Decisão

Usamos **New Relic** para APM, Kubernetes, Lambdas, logs e alertas:

| Camada | Instrumentação |
| --- | --- |
| EKS | `nri-bundle` via Helm no `fiapx-infra` (`eks-addons`): infraestrutura, eventos e logs do cluster |
| `video-api` e `video-processor` | agente **New Relic PHP** na imagem. Logs JSON (Monolog `JsonFormatter`) com `correlation_id`, `video_id`, `saga_id` e `user_id` |
| Lambdas (auth e notification) | layer New Relic para Node.js + logs JSON |
| SQS, Aurora, S3 | integração AWS ↔ New Relic via CloudWatch Metric Streams |

- **Correlação:** o `correlation_id` do envelope ([ADR-007](ADR-007-amazon-sqs-como-mensageria.md)) aparece em todos os logs, o que permite seguir um vídeo do upload à notificação.
- **Eventos customizados:** `VideoSagaTransition` (de, para, passo, duração) e `VideoProcessed` (duração, frames, tamanho).
- **Dashboard** versionado em `fiapx-docs/07-observabilidade/newrelic-dashboard.json`: vídeos por status (hoje), throughput de uploads, tempo de processamento p50/p95, taxa de falha, profundidade de cada fila e das DLQs, réplicas do worker ao longo do tempo, latência e erros do API Gateway e do `video-api`, sagas presas (`PROCESSING` com deadline vencido).
- **Alertas:**
  - mensagem em DLQ > 0 (alarme `ApproximateNumberOfMessagesVisible > 0` no CloudWatch, integrado ao New Relic);
  - taxa de falha > 10% em 15 min;
  - fila `processing-commands` com mais de 50 mensagens por 10 min;
  - erro 5xx > 2%;
  - sagas vencidas > 0.
- A licença do New Relic é um segredo: fica no Secrets Manager ou em GitHub Secrets, nunca no código.

## Alternativas consideradas

| Alternativa | Por que não |
| --- | --- |
| Prometheus + Grafana (recomendado no enunciado) | Exige operar e dimensionar Prometheus e Grafana no cluster e adicionar coleta de logs e de métricas das Lambdas à parte. Sem APM com traces por transação PHP |
| ELK (Elasticsearch, Logstash, Kibana) | Pesado para rodar no cluster. Forte em logs, mas sem APM e alertas equivalentes sem componentes extras |
| Só CloudWatch | Cobre métricas da AWS e logs, mas sem APM do PHP e com dashboards e correlação mais limitados |

A comparação completa está na RFC-010.

## Consequências

### Positivas

- Uma única ferramenta para APM, infraestrutura do Kubernetes, Lambdas, filas e logs, com correlação por `correlation_id`.
- Sem componentes de observabilidade para operar dentro do cluster além do `nri-bundle`.
- Dashboard e alertas versionados, prontos para a demonstração do vídeo.

### Negativas / riscos

- Dependência de um SaaS externo e da licença dele. O plano gratuito tem limite de ingestão de dados.
- O agente PHP aumenta a imagem e adiciona um pequeno overhead.
- Divergência com a stack recomendada pelo enunciado, que precisa ser justificada.
- O layer New Relic aumenta o cold start das Lambdas.

### Mitigações

- Logs em JSON estruturado e eventos customizados enxutos para controlar o volume ingerido. O ambiente fica desligado fora das demonstrações.
- A justificativa da escolha fica na RFC-010.
- Os logs continuam saindo no stdout e no CloudWatch, então há um fallback se o New Relic ficar indisponível.
