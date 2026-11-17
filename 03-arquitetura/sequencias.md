# Diagramas de sequência

Quatro fluxos: login, upload com processamento, falha com compensação e download.

## 1. Cadastro e login

```mermaid
sequenceDiagram
  autonumber
  actor U as Usuário
  participant GW as API Gateway
  participant REG as Lambda register
  participant LOG as Lambda login
  participant SM as Secrets Manager
  participant DB as Aurora fiapx_auth

  U->>GW: OPTIONS /api/auth/register (preflight CORS, o site está em outra origem)
  GW-->>U: 204 com Access-Control-Allow-Origin = URL do site (antes do authorizer)
  U->>GW: POST /api/auth/register {name, email, password}
  GW->>REG: invoca (sem authorizer)
  REG->>REG: valida e-mail e senha (mín. 8), bcrypt custo 12
  REG->>DB: INSERT users (e-mail único)
  REG-->>U: 201 {id, name, email}
  U->>GW: POST /api/auth/login {email, password}
  GW->>LOG: invoca (sem authorizer)
  LOG->>DB: SELECT por e-mail
  LOG->>LOG: bcrypt.compare
  LOG->>SM: lê a chave privada (cache no container da Lambda)
  LOG-->>U: 200 {access_token, token_type: Bearer, expires_in: 3600}
  Note over U,LOG: Erro de credencial sempre gera 401 com mensagem genérica
```

## 2. Upload e processamento com sucesso

```mermaid
sequenceDiagram
  autonumber
  actor U as Usuário
  participant GW as API Gateway
  participant AZ as Lambda authorizer
  participant V as video-api-web
  participant DB as Aurora fiapx_video
  participant S3
  participant QU as SQS video-uploaded
  participant C as saga-consumer
  participant R as outbox-relay
  participant QP as SQS processing-commands
  participant P as video-processor
  participant QR as SQS saga-replies.fifo

  U->>GW: POST /api/videos {filename, size_bytes, content_type} + Bearer
  GW->>AZ: valida JWT (RS256, iss, aud, exp), cache 300 s
  AZ-->>GW: autorizado + contexto do usuário
  GW->>V: requisição + x-user-id, x-user-email, x-user-name
  V->>DB: INSERT videos (PENDING_UPLOAD)
  V->>S3: gera POST pré-assinado (content-length-range até 500 MB, 1 h)
  V-->>U: 201 {id, status, upload: {url, fields, expires_at}}
  U->>S3: POST multipart (campos + arquivo por último)
  S3->>QU: ObjectCreated uploads/{video_id}.{ext}
  QU->>C: mensagem (long polling)
  C->>S3: HeadObject (existe, tamanho, tipo)
  C->>DB: BEGIN: saga STARTED → QUOTA_RESERVED → PROCESSING_REQUESTED, cota +1, vídeo QUEUED, outbox ProcessVideo, processed_messages, COMMIT
  C->>QU: DeleteMessage
  R->>DB: SELECT outbox pendente FOR UPDATE SKIP LOCKED
  R->>QP: SendMessage ProcessVideo
  R->>DB: UPDATE published_at
  QP->>P: ReceiveMessage (1 por pod)
  P->>QR: ProcessingStarted
  QR->>C: ProcessingStarted
  C->>DB: vídeo PROCESSING, saga PROCESSING (deadline renovado: agora + 30 min)
  P->>S3: GetObject (stream para /work)
  P->>P: ffmpeg -vf fps=1, zip (heartbeat a cada 60 s)
  P->>S3: PutObject results/{video_id}/frames.zip
  P->>QR: VideoProcessed {zip_key, frame_count, zip_size_bytes, duration_ms}
  P->>QP: DeleteMessage
  QR->>C: VideoProcessed
  C->>DB: BEGIN: vídeo COMPLETED, cota -1, saga COMPLETED, outbox SendNotification (opcional), COMMIT
```

## 3. Falha no processamento com compensação

```mermaid
sequenceDiagram
  autonumber
  participant P as video-processor
  participant QR as SQS saga-replies.fifo
  participant C as saga-consumer
  participant DB as Aurora fiapx_video
  participant R as outbox-relay
  participant QP as SQS processing-commands
  participant QN as SQS notification-commands
  participant N as Lambda notification
  participant DD as DynamoDB notifications
  participant SMTP as Provedor SMTP (Brevo)
  actor U as Usuário

  P->>P: ffmpeg falha (arquivo corrompido)
  P->>QR: VideoProcessingFailed {error_code: FFMPEG_ERROR, attempt}
  P->>QP: DeleteMessage (falha definitiva)
  QR->>C: VideoProcessingFailed
  C->>DB: saga COMPENSATING, outbox CleanupArtifacts
  R->>QP: CleanupArtifacts {bucket, prefix: results/{video_id}/}
  QP->>P: CleanupArtifacts
  P->>P: apaga objetos parciais do prefixo
  P->>QR: ArtifactsCleaned {deleted_objects}
  QR->>C: ArtifactsCleaned
  C->>DB: BEGIN: ReleaseQuota (cota -1), vídeo FAILED + failure_reason, saga COMPENSATED, outbox SendNotification VIDEO_FAILED, COMMIT
  R->>QN: SendNotification
  QN->>N: lote (batch size 10)
  N->>DD: PutItem PENDING, condição attribute_not_exists(message_id) OR status = FAILED
  N->>SMTP: envia por SMTP autenticado (Nodemailer, STARTTLS)
  SMTP-->>N: provider_message_id
  N->>DD: UpdateItem SENT
  N->>QR: NotificationSent
  SMTP-->>U: e-mail "Não conseguimos processar o seu vídeo"
  QR->>C: NotificationSent
  C->>DB: saga NOTIFIED
```

### Timeout

```mermaid
sequenceDiagram
  autonumber
  participant CR as CronJob schedule:run
  participant DB as Aurora fiapx_video
  participant R as outbox-relay
  participant QP as SQS processing-commands

  CR->>DB: saga:check-timeouts: sagas PROCESSING com deadline_at vencido
  CR->>DB: saga COMPENSATING (motivo PROCESSING_TIMEOUT), outbox CleanupArtifacts
  R->>QP: CleanupArtifacts
  Note over CR,QP: Daqui em diante o fluxo é igual ao da falha (ArtifactsCleaned → ReleaseQuota → FAILED → e-mail)
```

## 4. Consulta e download

```mermaid
sequenceDiagram
  autonumber
  actor U as Usuário
  participant GW as API Gateway
  participant V as video-api-web
  participant DB as Aurora fiapx_video
  participant S3

  loop a cada 5 s enquanto houver status não final
    U->>GW: GET /api/videos?page=1&per_page=10
    GW->>V: requisição autorizada + x-user-id
    V->>DB: SELECT ... WHERE user_id = ? ORDER BY created_at DESC
    V-->>U: 200 {data: [Video], meta: {page, per_page, total}}
  end
  U->>GW: GET /api/videos/{id}/download
  GW->>V: requisição autorizada
  V->>DB: busca o vídeo do usuário
  alt status COMPLETED
    V->>S3: GET pré-assinado de results/{id}/frames.zip (15 min)
    V-->>U: 200 {url, expires_at}
    U->>S3: GET url (download direto)
  else outro status
    V-->>U: 409 {message: "O vídeo ainda não foi processado"}
  else vídeo de outro usuário ou inexistente
    V-->>U: 404
  end
```

## 5. Recuperação e troca de senha

```mermaid
sequenceDiagram
  autonumber
  actor U as Usuário
  participant GW as API Gateway
  participant PW as Lambda password
  participant DB as Aurora fiapx_auth
  participant QN as SQS notification-commands
  participant N as Lambda notification
  participant SMTP as Provedor SMTP (Brevo)

  U->>GW: POST /api/auth/password/forgot {email}
  GW->>PW: invoca (sem authorizer, rate limit restrito)
  PW->>DB: busca usuário pelo e-mail
  alt e-mail cadastrado
    PW->>DB: invalida tokens abertos e grava hash SHA-256 do novo token (expira em 30 min)
    PW->>QN: SendNotification PASSWORD_RESET (saga_id nulo, action_url com o token)
    QN->>N: SendNotification
    N->>SMTP: envia o e-mail com o link
    SMTP-->>U: e-mail "Redefina sua senha"
  end
  PW-->>U: 202 (mesma resposta em qualquer caso)
  U->>GW: POST /api/auth/password/reset/verify {token}
  GW->>PW: invoca
  PW->>DB: busca pelo hash, confere expires_at e used_at
  PW-->>U: 200 {email_masked, expires_at} ou 422 genérico
  U->>GW: POST /api/auth/password/reset {token, password}
  GW->>PW: invoca
  PW->>DB: BEGIN: nova senha (bcrypt 12), token used_at, COMMIT
  PW->>QN: SendNotification PASSWORD_CHANGED
  PW-->>U: 200 {access_token, token_type, expires_in}
  Note over U,PW: Troca logado: PUT /api/auth/password {current_password, new_password}<br/>passa pelo authorizer, confere a senha atual, troca e envia PASSWORD_CHANGED (204)
```
