# RFC-005 — Escala do processamento

- **Status:** Aprovada
- **Data:** 2026-11-16
- **Autores:** Diego Fenille, Eduardo Santos
- **ADR resultante:** ADR-009

## Resumo

Propomos rodar o `fiapx-video-processor` (PHP 8.4.27 + Laravel 13 + `ffmpeg`) como Deployment no EKS,
com **um vídeo por pod** e escala horizontal pelo **KEDA** com base na profundidade da fila
`processing-commands` (`aws-sqs-queue`, `queueLength: 1`, de 1 a 10 réplicas). Durante o `ffmpeg`, o
worker estende o visibility timeout da mensagem (heartbeat).

## Motivação

O RF1 exige processar mais de um vídeo ao mesmo tempo, e o RF2 exige não perder requisições em picos.
Extrair frames é uma carga **longa, variável e intensa em CPU e disco**: depende da duração do vídeo,
gera centenas de PNGs temporários e um zip que pode ter centenas de MB. No projeto base, tudo rodava
dentro da requisição HTTP, sem concorrência controlada.

A métrica que representa a demanda é o **trabalho pendente na fila**, não o uso de CPU dos pods que
já estão ocupados.

## Proposta

- `php artisan processor:consume`: `ReceiveMessage` com long polling de 20 s, uma mensagem por vez;
  `DeleteMessage` **só depois** de subir o zip e publicar a resposta na `saga-replies.fifo`.
- **Heartbeat:** `VisibilityHeartbeat` chama `ChangeMessageVisibility` a cada 60 s (+300 s) enquanto o
  `ffmpeg` roda; se o pod morrer, a mensagem volta para a fila.
- **KEDA `ScaledObject`:** `aws-sqs-queue`, `queueLength: 1`, `minReplicaCount: 1`,
  `maxReplicaCount: 10`; o KEDA usa a permissão `sqs:GetQueueAttributes` (Pod Identity).
- **Recursos:** `/work` em `emptyDir` com `sizeLimit` (ex.: 10Gi), limpo no `finally`; requests e limits
  de CPU e memória definidos para caber nos nós do managed node group.
- **Graceful shutdown:** `SIGTERM` tratado com `pcntl`; o pod termina o vídeo atual e não pega novas
  mensagens; `terminationGracePeriodSeconds` maior que o processamento máximo esperado.
- **Falhas:** definitiva (vídeo corrompido, `NO_FRAMES`) → `VideoProcessingFailed` imediato; transitória
  (S3, rede) → a mensagem volta e, após 3 tentativas, vai para a DLQ; o timeout da SAGA compensa.
- **Concorrência por usuário:** limitada pela cota (`processing_quotas.max_parallel`, padrão 5).

## Alternativas

| Critério | KEDA por fila no EKS (proposta) | HPA por CPU no EKS | Lambda com imagem de container | AWS Batch |
| --- | --- | --- | --- | --- |
| Sinal de escala | Mensagens na fila: reage à demanda real | CPU dos pods: reage depois, e pod ocioso em long polling não usa CPU | Uma invocação por mensagem (event source mapping) | Jobs submetidos na job queue |
| Vídeos longos | Sem limite de duração (heartbeat) | Sem limite | **Limite de 15 min** por invocação | Sem limite |
| Disco e memória | Configuráveis (`emptyDir`, limits do pod) | Configuráveis | **Até 10 GB** de memória e 10 GB de `/tmp` | Configuráveis |
| Latência para começar | Baixa (1 réplica mínima quente) | Baixa | Baixa (cold start da imagem) | Alta (provisionar instância/Fargate) |
| Escala a partir de zero | Possível (`minReplicaCount: 0`) | Não | Sim | Sim |
| Custo aproximado | Nós do EKS já pagos; escala com a fila | Igual, mas escala pior | Por uso; caro em vídeos longos | Por uso; sem control plane extra |
| Complexidade operacional | Média (KEDA via Helm no `eks-addons`) | Baixa | Baixa | Alta (compute environment, job definition, integração com a SAGA) |
| Reuso de código e imagem | Mesma stack Laravel e Dockerfile | Igual | Exige adaptar a imagem ao runtime da Lambda (Bref ou RIC) | Precisa de um disparador da fila para o Batch |
| Aderência ao enunciado (Kubernetes + mensageria) | Alta | Média | Média (sai do Kubernetes) | Média |
| Curva de aprendizado do time | Média: EKS e HPA conhecidos das Fases 3 e 4; KEDA novo | Baixa | Média | Alta |

## Riscos

- **Teto de 10 réplicas** em picos muito grandes: a fila cresce, mas nada se perde (RF2). Ajustável no
  `ScaledObject` e no node group.
- **Falta de nós** para novas réplicas. Mitigação: requests realistas; Cluster Autoscaler ou Karpenter
  ficam como evolução.
- **Mensagem reprocessada** se o heartbeat falhar. Mitigação: worker idempotente por
  `results/{video_id}/frames.zip` e SAGA idempotente.
- **Disco cheio** com vídeos grandes. Mitigação: limite de 500 MB no upload (RFC-002) e `sizeLimit`.
- **Scale-in interrompendo vídeo em andamento.** Mitigação: graceful shutdown e grace period longo.
- **Custo de 1 réplica sempre ligada.** Aceito para reduzir latência na demonstração; pode ir a 0.

## Decisão

Aprovada: worker Laravel no EKS, um vídeo por pod, escalado por KEDA pela fila `processing-commands`
(1 a 10 réplicas), com heartbeat de visibility e graceful shutdown. A decisão é registrada na
**ADR-009**.
