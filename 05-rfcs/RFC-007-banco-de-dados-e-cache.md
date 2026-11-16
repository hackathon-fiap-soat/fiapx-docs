# RFC-007 — Banco de dados e cache

- **Status:** Aprovada
- **Data:** 2026-11-16
- **Autores:** Diego Fenille, Eduardo Santos
- **ADR resultante:** ADR-005

## Resumo

Propomos **um cluster Aurora MySQL v3 (compatível com MySQL 8.0) Serverless v2** (0,5 a 4 ACU), com
**um database e um usuário por serviço** (`fiapx_auth` e `fiapx_video`) e nenhum acesso cruzado. Os
arquivos ficam no S3 e o histórico de notificações no DynamoDB (RFC-008). **Não adotamos Redis**: não
há, hoje, um caso de uso que precise de cache ou sessão em memória.

O enunciado recomenda PostgreSQL + Redis. **Divergimos de forma consciente**; abaixo mostramos que o
requisito por trás da recomendação (RT1 persistência e RT2 escalabilidade) continua atendido.

## Motivação

Precisamos persistir usuários, vídeos, estado da SAGA, cota, outbox e mensagens processadas, com
**transações ACID**: o outbox só funciona se a mudança de estado e o comando forem gravados na mesma
transação, e a reserva de cota precisa de atualização atômica. Também queremos:

- continuidade com o que o time domina: as **Fases 1 a 4** foram feitas em **Laravel + MySQL** (RDS
  MySQL na AWS nas Fases 3 e 4), com migrations, Eloquent e scripts já conhecidos;
- custo baixo fora das demonstrações e escala sem troca de instância;
- "database por serviço" sem pagar um cluster por serviço.

## Proposta

- Aurora MySQL Serverless v2, subnets privadas, secret do master no Secrets Manager.
- `fiapx-infra/sql/create-databases.sql` cria `fiapx_auth`, `fiapx_video` e usuários com `GRANT` mínimo
  (entregável "script de criação do banco").
- `fiapx_auth.users` (dono: `fiapx-auth`); `fiapx_video.videos`, `processing_sagas` (lock otimista em
  `version`), `processing_quotas`, `outbox_messages` e `processed_messages` (dono: `fiapx-video-api`).
- IDs UUID v7 em `CHAR(36)`; `user_id` em `videos` é referência lógica, sem FK entre databases.
- Outbox com `SELECT ... FOR UPDATE SKIP LOCKED` (suportado pelo MySQL 8.0).
- Local: `mysql:8.0` no `docker-compose` do `fiapx-infra/local`.

### Por que não Redis

| Uso típico do Redis | Como resolvemos sem Redis |
| --- | --- |
| Sessão de usuário | JWT RS256 stateless; nenhuma sessão no servidor |
| Cache de autenticação | Cache do Lambda Authorizer no API Gateway por 300 s |
| Fila de jobs do Laravel | SQS (RFC-006), durável e com DLQ |
| Idempotência e deduplicação | `processed_messages` no MySQL e `attribute_not_exists` no DynamoDB, na mesma transação/condição do efeito |
| Lock distribuído | `FOR UPDATE SKIP LOCKED` e lock otimista no MySQL |
| Cache de leitura | Listagem paginada por índice `idx_videos_user_created`; volume baixo |

Redis (ElastiCache) fica como **evolução futura** se surgir um hot path de leitura, por exemplo polling
intenso da lista de status em larga escala.

## Alternativas

| Critério | Aurora MySQL Serverless v2 (proposta) | RDS MySQL | Aurora PostgreSQL + Redis (**recomendado no enunciado**) | DynamoDB |
| --- | --- | --- | --- | --- |
| Transações ACID para outbox e cota | Sim | Sim | Sim | Limitadas (`TransactWriteItems`, sem SQL) |
| Experiência do time | Alta (Fases 1–4 em MySQL) | Alta | Média no PostgreSQL; Redis sem caso de uso | Baixa para o modelo relacional |
| Escalabilidade | Automática em ACU (0,5–4) | Troca manual de classe | Automática (Aurora) + nó de cache | Automática |
| Custo aproximado | Baixo/médio; cobra por ACU usada | Instância fixa 24 h | Aurora + nó ElastiCache sempre ligado | Muito baixo neste volume |
| Complexidade operacional | Baixa | Baixa | Média (dois sistemas, invalidação de cache) | Baixa, mas modelagem por padrão de acesso |
| Database por serviço no mesmo cluster | Sim | Sim | Sim | Uma tabela por serviço |
| Suporte do Laravel e do `mysql2` | Nativo | Nativo | Nativo | Pacotes de terceiros |
| Lock-in | Baixo (protocolo MySQL) | Baixo | Baixo | Alto |
| Aderência ao enunciado | Atende RT1/RT2; diverge do produto recomendado | Atende | **Recomendado** | Atende persistência |

## Riscos

- **Divergência da stack recomendada.** Mitigação: esta RFC e a ADR-005 mostram que persistência,
  escala e consistência estão atendidas; a troca para PostgreSQL afetaria só a Infrastructure.
- **Cluster compartilhado como ponto único de falha.** Aceito no escopo do hackathon; Aurora replica o
  storage em 3 AZs e permite adicionar réplica de leitura.
- **Escala mínima de 0,5 ACU gera custo contínuo.** Mitigação: `terraform destroy` fora das
  demonstrações.
- **Ausência de cache** se o polling crescer. Mitigação: métricas de latência no New Relic e Redis como
  evolução documentada.
- **Lambdas abrindo muitas conexões.** Mitigação: conexão reaproveitada entre invocações; RDS Proxy
  como evolução.

## Decisão

Aprovada: Aurora MySQL Serverless v2 com um database e um usuário por serviço no mesmo cluster, sem
Redis, divergindo conscientemente de PostgreSQL + Redis sem perder RT1 e RT2. A decisão é registrada na
**ADR-005**.
