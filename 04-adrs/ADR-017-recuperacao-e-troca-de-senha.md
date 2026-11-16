# ADR-017 — Recuperação e troca de senha no `fiapx-auth`, com e-mail pelo `fiapx-notification`

- **Status:** Aceito
- **Data:** 2026-11-16
- **Decisores:** Diego Fenille, Eduardo Santos
- **Relacionados:** [ADR-004](ADR-004-autenticacao-api-gateway-lambda-authorizer-jwt-rs256.md), [ADR-013](ADR-013-notificacao-sqs-lambda-ses-e-historico-no-dynamodb.md), [ADR-015](ADR-015-remetente-de-email-dominio-proprio-e-sandbox-do-ses.md)

## Contexto

O layout do front-end gerado pelo time (Google Stitch, versionado no `fiapx-web`) tem as telas
"Recuperar senha", "Criar nova senha" (aberta pelo link do e-mail) e a seção "Segurança e troca de
senha" do perfil. O escopo inicial não previa essas funções, e o time decidiu incluí-las. O resto da tela
de perfil continua fora do escopo.

O layout também define a política de senha (mínimo de 8 caracteres, com letra maiúscula, número e
símbolo) e a validade do link (30 minutos, uso único).

Restrições:

- A resposta não pode revelar se um e-mail tem cadastro (mesma regra do cadastro e do login).
- O SES está em sandbox: só envia para destinatários verificados, o que basta para a demonstração.
- O envio de e-mail já é responsabilidade do `fiapx-notification`, com idempotência e histórico no DynamoDB.

## Decisão

### Endpoints (Lambda `password` no `fiapx-auth`)

| Rota | Autenticação | Resultado |
|---|---|---|
| `POST /api/auth/password/forgot` `{email}` | Não | Sempre `202`, exista ou não o e-mail |
| `POST /api/auth/password/reset/verify` `{token}` | Não | `200 {email_masked, expires_at}` ou `422` genérico |
| `POST /api/auth/password/reset` `{token, password}` | Não | `200` com JWT (troca a senha e já entra) ou `422` genérico |
| `PUT /api/auth/password` `{current_password, new_password}` | Sim (authorizer) | `204` ou `422` |

Uma única Lambda atende as quatro rotas, para não multiplicar funções com o mesmo código e permissões.

### Token de redefinição

- 32 bytes aleatórios (`crypto.randomBytes`), enviados em base64url no link
  `<web_url>/redefinir-senha?token=...`.
- No banco fica só o **hash SHA-256** do token, na tabela `fiapx_auth.password_reset_tokens`, com
  `expires_at` (agora + 30 min) e `used_at`.
- Uso único: o reset marca `used_at` na mesma transação da troca de senha.
- Um pedido novo invalida os tokens anteriores ainda não usados do mesmo usuário.
- Token inexistente, expirado ou usado recebem a mesma resposta (`422`, "O link de redefinição é inválido
  ou expirou").
- O token vai sempre no **corpo** das requisições à API, nunca na URL da API, para não aparecer em logs
  de acesso do CloudFront e do API Gateway.

### Política de senha

Mínimo de 8 e máximo de 72 caracteres (limite do bcrypt), com pelo menos uma letra maiúscula, um número
e um símbolo. Vale para cadastro, redefinição e troca. A nova senha deve ser diferente da atual.

### E-mail pelo `fiapx-notification`

- O `fiapx-auth` publica `SendNotification` na fila `notification-commands`, com os templates novos
  `PASSWORD_RESET` (com `action_url`) e `PASSWORD_CHANGED` (confirmação após reset ou troca).
- Essas mensagens estão fora da SAGA: `saga_id` e `video_id` são `null` no envelope, e o
  `fiapx-notification` não publica resposta na `saga-replies.fifo` quando `saga_id` é nulo.
- O `action_url` não é gravado no DynamoDB nem em log (contém o token).
- A publicação é direta, sem outbox: se o envio à fila falhar, a Lambda responde erro e o usuário pede o
  link de novo. Não há estado de negócio a proteger além do token já gravado.

### Proteção contra abuso

Rate limit mais restrito nas rotas `/api/auth/password/*` no stage do API Gateway, além do throttling
geral. No máximo um e-mail de redefinição a cada 2 minutos por usuário (o layout informa esse intervalo).

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Amazon Cognito para recuperação de senha | Exigiria migrar toda a autenticação (descartado na RFC-004) |
| `fiapx-auth` enviando e-mail direto pelo SES | Duplicaria templates, remetente, histórico e idempotência que já existem no `fiapx-notification` |
| Nova mensagem `SendPasswordEmail` em vez de reutilizar `SendNotification` | Mais um contrato e mais um handler para o mesmo efeito (enviar um e-mail com template) |
| Token JWT assinado como link de redefinição | Não é de uso único sem guardar estado; o hash no banco resolve uso único e invalidação |
| Código numérico de 6 dígitos por e-mail | O layout usa link; código curto exige limite de tentativas mais rígido |

## Consequências

### Positivas

- As telas do layout ficam cobertas pelo back-end.
- Um único caminho de e-mail para toda a plataforma, com histórico no DynamoDB.
- O token não pode ser reaproveitado nem lido do banco.

### Negativas / riscos

- O envelope passa a aceitar `saga_id` e `video_id` nulos, mas só em `SendNotification` (o schema do
  envelope exige os dois nas demais mensagens).
- O `fiapx-auth` passa a depender da fila do `fiapx-notification`: a ordem de deploy muda
  (`fiapx-notification` antes do `fiapx-auth`).
- Tokens JWT emitidos antes da troca de senha continuam válidos até expirar (no máximo 1 hora, mais os
  300 s de cache do authorizer), porque o JWT é stateless e o authorizer não consulta o banco.
- Em sandbox, o e-mail de redefinição só chega a endereços verificados no SES.

### Mitigações

- Validade curta do JWT (1 h) e e-mail `PASSWORD_CHANGED` avisando o usuário de toda troca.
- Contract tests no `fiapx-auth` e no `fiapx-notification` com o exemplo
  `send-notification.v1--password-reset.json`.
- Usuários de demonstração com e-mail verificado no SES.
