# RFC-010 — Observabilidade

- **Status:** Aprovada
- **Data:** 2026-11-16
- **Autores:** Diego Fenille, Eduardo Santos
- **ADR resultante:** ADR-011

## Resumo

Propomos o **New Relic** como plataforma única de observabilidade: APM PHP no `video-api` e no
`video-processor`, `nri-bundle` no EKS, layer Node.js nas Lambdas, integração AWS por CloudWatch Metric
Streams (SQS, Aurora, S3, API Gateway), logs JSON correlacionados, eventos customizados, dashboard
versionado e alertas.

O enunciado recomenda Prometheus + Grafana (ou ELK). **Divergimos de forma consciente**; esta RFC mostra
que o requisito por trás da recomendação continua atendido.

## Motivação

A recomendação existe para que o time consiga **ver métricas, logs e falhas de um sistema distribuído e
ser avisado quando algo dá errado**. No FIAP X, uma requisição atravessa CloudFront, API Gateway, Lambda,
EKS, SQS, S3, SES e DynamoDB. Precisamos:

- seguir um vídeo de ponta a ponta (`correlation_id`, `saga_id`, `video_id`, `user_id`);
- enxergar a profundidade das filas e das DLQs e o KEDA escalando o worker (evidência do RF1/RF2);
- alertar sobre falhas e sagas presas;
- fazer isso sem operar mais uma pilha de servidores durante o hackathon.

O time já usou New Relic na Fase 3 e o manteve na Fase 4, com evidências entregues.

## Proposta

- **EKS:** `nri-bundle` (Helm) no `fiapx-infra/modules/eks-addons`: infraestrutura, eventos e logs.
- **PHP:** agente New Relic na imagem; Monolog `JsonFormatter` com `correlation_id`, `video_id`,
  `saga_id` e `user_id`.
- **Lambdas:** layer New Relic para Node.js + logs JSON.
- **AWS:** CloudWatch Metric Streams → New Relic; alarmes de DLQ no CloudWatch integrados.
- **Eventos customizados:** `VideoSagaTransition` (de, para, passo, duração) e `VideoProcessed`
  (duração, frames, tamanho).
- **Dashboard** versionado em `fiapx-docs/07-observabilidade/newrelic-dashboard.json`: vídeos por status,
  throughput de uploads, processamento p50/p95, taxa de falha, filas e DLQs, réplicas do worker,
  latência e erros do API Gateway e do `video-api`, sagas presas.
- **Alertas:** DLQ > 0; falha > 10% em 15 min; `processing-commands` > 50 mensagens por 10 min;
  5xx > 2%; sagas vencidas > 0.

### Como o requisito do enunciado continua atendido

| Capacidade | Prometheus + Grafana | New Relic |
| --- | --- | --- |
| Métricas de infraestrutura e Kubernetes | Prometheus + kube-state-metrics + node-exporter | `nri-bundle` |
| Métricas de aplicação | Exporters e instrumentação manual | APM PHP/Node.js automático + eventos customizados |
| Métricas de serviços AWS | `cloudwatch_exporter` | Metric Streams nativo |
| Dashboards | Grafana | Dashboards (JSON versionado no `fiapx-docs`) |
| Alertas | Alertmanager | Alert policies + integração com CloudWatch |
| Logs e traces | Loki/Tempo ou ELK à parte | Inclusos, correlacionados com APM |

## Alternativas

| Critério | New Relic (proposta) | Prometheus + Grafana (**recomendado no enunciado**) | ELK (Elasticsearch, Logstash, Kibana) | CloudWatch |
| --- | --- | --- | --- | --- |
| Cobertura (métricas, logs, traces, APM) | Completa em um só lugar | Métricas; logs e traces exigem Loki/Tempo | Forte em logs; métricas e APM à parte | Completa, mas fragmentada (X-Ray, Logs Insights) |
| Instrumentação de PHP e Lambda | Agente e layer prontos | Exporter/OpenTelemetry manual | Beats/APM agents | Nativa nas Lambdas; PHP precisa de agente |
| Complexidade operacional | Baixa (SaaS) | Alta (rodar, persistir e escalar no cluster) | Alta (cluster Elasticsearch pesado) | Baixa |
| Custo aproximado | Camada gratuita cobre o volume do hackathon | Software livre, mas consome nós do EKS e storage | Alto em recursos (memória e disco) | Por métrica, log e alarme; baixo neste volume |
| Lock-in | Médio (SaaS; agentes proprietários) | Baixo | Baixo | Alto |
| Correlação ponta a ponta | Distributed tracing nativo | Requer Tempo + OpenTelemetry | Requer APM | X-Ray, parcial no PHP |
| Curva de aprendizado do time | Baixa (Fases 3 e 4) | Média | Alta | Média |
| Aderência ao enunciado | Diverge do produto, atende o requisito | **Recomendado** | **Alternativa citada** | Diverge, atende parcialmente |

## Riscos

- **Divergência da stack recomendada.** Mitigação: esta RFC, a ADR-011 e a tabela de equivalência; o
  vídeo de entrega mostra dashboard e alertas com dados reais.
- **Limites da camada gratuita** (ingestão e usuários). Mitigação: logs em nível `info`, amostragem e
  ambiente desligado fora das demonstrações.
- **Dependência de SaaS externo.** Mitigação: alarmes críticos de DLQ também no CloudWatch; logs JSON
  com campos padronizados facilitam migrar para OpenTelemetry.
- **License key vazada.** Mitigação: Secrets Manager/GitHub Secrets, nunca no repositório.
- **Overhead do agente PHP** no worker. Baixo frente ao custo do `ffmpeg`; monitorado no próprio APM.

## Decisão

Aprovada: New Relic para APM, Kubernetes, Lambdas, logs, dashboard e alertas, divergindo
conscientemente de Prometheus + Grafana sem perder a capacidade de monitorar, correlacionar e alertar.
A decisão é registrada na **ADR-011**.
