# RFC-008 — Registro de notificações

- **Status:** Aprovada
- **Data:** 2026-11-16
- **Autores:** Diego Fenille, Eduardo Santos
- **ADR resultante:** ADR-013

## Resumo

Propomos que o `fiapx-notification` seja um serviço autônomo: fila própria `notification-commands` →
**Lambda Node.js 24** → **Amazon SES**, com cada envio registrado na tabela **DynamoDB**
`fiapx-<env>-notifications` (partition key `email`, sort key `message_id`). A tabela serve ao mesmo
tempo de **histórico** por destinatário e de **controle de idempotência** do envio.

## Motivação

O RF5 exige notificar o usuário em caso de erro. A SAGA envia `SendNotification` (`VIDEO_FAILED`
obrigatório, `VIDEO_COMPLETED` opcional) e espera `NotificationSent` ou `NotificationFailed`. Precisamos:

- **não enviar o mesmo e-mail duas vezes** quando o SQS reentregar a mensagem;
- responder à SAGA mesmo em reentrega (sem reenviar o e-mail);
- consultar "todos os envios para o e-mail X" para suporte e para a demonstração;
- manter o serviço de Notificação dono dos próprios dados, sem acessar o database de outro serviço.

## Proposta

| Atributo | Papel |
| --- | --- |
| `email` | Partition key: destinatário normalizado em minúsculas |
| `message_id` | Sort key: id do `SendNotification`; base da idempotência |
| `created_at` | Sort key do LSI `email-created_at-index` (histórico cronológico) |
| `status` | `PENDING`, `SENT`, `FAILED`, `DELIVERED`, `BOUNCED`, `COMPLAINED` |
| `template`, `subject`, `video_id`, `saga_id`, `correlation_id` | Conteúdo e rastreabilidade com a SAGA |
| `ses_message_id`, `attempts`, `last_error`, `sent_at`, `updated_at` | Resultado do envio |
| `expires_at` | TTL de 90 dias |

- `PutItem` condicional: `attribute_not_exists(message_id) OR #status = :failed` (só reenvia o que falhou).
- Se o item já está `SENT`, a Lambda responde `NotificationSent` sem chamar o SES.
- Erro no SES: `status = FAILED`, `attempts + 1` e `ReportBatchItemFailures`; na 3ª tentativa,
  `NotificationFailed` e a mensagem vai para a `notification-commands-dlq`.
- Billing `PAY_PER_REQUEST`, PITR ligado, criptografia padrão; tabela criada pelo Terraform em
  `fiapx-notification/infra` com `prevent_destroy`.
- Opcional: eventos do configuration set do SES atualizam o item para `DELIVERED`, `BOUNCED` ou
  `COMPLAINED`.
- Local: DynamoDB no LocalStack e e-mail no Mailpit (`EMAIL_DRIVER=smtp`).

## Alternativas

| Critério | DynamoDB (proposta) | Tabela no Aurora | Apenas logs (New Relic/CloudWatch) |
| --- | --- | --- | --- |
| Idempotência do envio | Escrita condicional atômica por `email` + `message_id` | `UNIQUE` + transação | Não garante: log não impede reenvio |
| Histórico por destinatário | `Query` no LSI por `email` | `SELECT` com índice | Busca em logs, sujeita à retenção |
| Autonomia do serviço | Total: tabela do próprio repositório | Exige database e usuário novos no cluster compartilhado | Total |
| Conexão a partir da Lambda | HTTP, sem pool, sem VPC obrigatória | Conexões MySQL a cada cold start | Nenhuma |
| Escalabilidade | Automática, sem capacidade a planejar | Limitada pelo cluster (0,5–4 ACU) | Automática |
| Custo aproximado | Muito baixo (por requisição) | Incluso no Aurora, mas disputa ACU | Baixo |
| Expiração de dados | TTL nativo (90 dias) | Job de limpeza | Retenção do log |
| Complexidade operacional | Baixa | Baixa | Muito baixa |
| Aderência ao enunciado e à avaliação | Demonstra persistência NoSQL e poliglota | Atende | Fraca: não é persistência consultável |
| Curva de aprendizado do time | Média (modelagem por padrão de acesso) | Baixa | Baixa |
| Lock-in | Alto (API do DynamoDB, isolada em `DynamoNotificationRepository`) | Baixo | Médio |

## Riscos

- **Partition key por e-mail** concentra itens de um destinatário. Aceitável: volume por usuário é baixo
  e o LSI cobre a consulta cronológica.
- **LSI limita a coleção por partition key a 10 GB.** Muito acima do esperado com TTL de 90 dias.
- **Dado pessoal (e-mail) armazenado.** Mitigação: criptografia padrão, TTL e acesso IAM restrito à
  Lambda.
- **Falha entre o envio no SES e o `UpdateItem`** pode gerar reenvio raro. Aceito: o SES devolve
  `ses_message_id` e o risco é um e-mail duplicado, não a perda da notificação.
- **Sandbox do SES** só envia para destinatários verificados. Mitigação: ADR-015 e mailbox simulator nos
  testes.

## Decisão

Aprovada: histórico e idempotência das notificações no DynamoDB, com PK `email`, SK `message_id`, LSI por
`created_at` e TTL de 90 dias, em um serviço SQS → Lambda → SES independente. A decisão é registrada na
**ADR-013**.
