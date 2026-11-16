# Projeto Hackathon FIAP X — Especificação para o Agente Executor

> **Para quem é este documento:** um agente de IA (ou dev) que vai **criar do zero** todos os repositórios,
> a documentação, a infraestrutura e o código do Hackathon da Fase 5 (POSTECH SOAT).
> Leia o documento inteiro antes de começar. Siga a ordem das etapas (§12) e **pare nos pontos de aprovação**.
>
> Fontes: `POSTECH - SOAT - Fase 5 - Hacka.pdf` (enunciado, na raiz deste workspace e em `/Applications/XAMPP/xamppfiles/htdocs/pos/tech-challenge-application/docs/Fase5/`),
> `FASE5.md` (análise inicial) e as entregas das Fases 1–4 em `/Applications/XAMPP/xamppfiles/htdocs/pos/tech-challenge-application/docs/Fase1` … `Fase4`
> (repositório `tech-challenge-application`, padrões já adotados pelo time).

---

## Sumário

1. [Contexto e objetivo](#1-contexto-e-objetivo)
2. [Requisitos (enunciado)](#2-requisitos-enunciado)
3. [Stack obrigatória e decisões fechadas](#3-stack-obrigatória-e-decisões-fechadas)
4. [Repositórios](#4-repositórios)
5. [Arquitetura](#5-arquitetura)
6. [SAGA orquestrada do processamento](#6-saga-orquestrada-do-processamento)
7. [Mensageria e contratos](#7-mensageria-e-contratos)
8. [Especificação por repositório](#8-especificação-por-repositório)
9. [Banco de dados](#9-banco-de-dados)
10. [Observabilidade](#10-observabilidade)
11. [CI/CD e fluxo de deploy](#11-cicd-e-fluxo-de-deploy)
12. [Plano de execução para o agente](#12-plano-de-execução-para-o-agente)
13. [Regras para o agente](#13-regras-para-o-agente)
14. [Entregáveis finais e checklist](#14-entregáveis-finais-e-checklist)

---

## 1. Contexto e objetivo

A empresa fictícia **FIAP X** tem um protótipo que recebe um vídeo, extrai um frame por segundo com
`ffmpeg` e devolve as imagens em um `.zip`. O protótipo (projeto base) é um único `main.go` (Go + Gin)
que:

- processa o vídeo **de forma síncrona** dentro do `POST /upload`;
- grava tudo em **disco local** (`uploads/`, `outputs/`, `temp/`);
- não tem **autenticação**, **banco de dados**, **fila**, **testes** nem **tratamento de falhas**;
- tem um Dockerfile marcado como "exemplo de como NÃO fazer".

Lógica a preservar do projeto base (é o "core" do negócio):

```bash
ffmpeg -i <video> -vf fps=1 -y <tempDir>/frame_%04d.png   # extrai 1 frame/s
# zipa todos os frame_*.png em frames_<id>.zip
# formatos aceitos: mp4, avi, mov, mkv, wmv, flv, webm (os mesmos do projeto base)
```

**Objetivo:** reconstruir o sistema como uma solução distribuída, escalável e resiliente na AWS, aplicando
DDD + Clean Architecture, microsserviços, mensageria, SAGA, testes, CI/CD e observabilidade.

---

## 2. Requisitos (enunciado)

### Funcionais

| ID | Requisito | Como atendemos |
|---|---|---|
| RF1 | Processar **mais de um vídeo ao mesmo tempo** | Workers no EKS escalados pelo tamanho da fila (KEDA). Cada pod processa 1 vídeo e N pods rodam em paralelo |
| RF2 | Em picos, **não perder nenhuma requisição** | Upload direto ao S3 + evento S3 → SQS (durável) + outbox transacional + DLQ + consumidores idempotentes |
| RF3 | Sistema protegido por **usuário e senha** | API Gateway + Lambda Node.js (register/login, bcrypt, JWT RS256) + Lambda Authorizer |
| RF4 | **Listagem de status** dos vídeos do usuário | `GET /api/videos` paginado e filtrado pelo usuário do token |
| RF5 | Em caso de erro, **notificar o usuário** | A SAGA envia o comando `SendNotification` → Lambda de notificação → e-mail via Amazon SES |

### Técnicos

| ID | Requisito | Como atendemos |
|---|---|---|
| RT1 | Persistir os dados | Aurora MySQL (dados) + S3 (arquivos) |
| RT2 | Arquitetura escalável | EKS + HPA (API) + KEDA (worker) + serviços gerenciados (SQS, S3, Aurora Serverless v2, Lambda) |
| RT3 | Versionado no GitHub | Um repositório por serviço (§4) |
| RT4 | Testes que garantam a qualidade | Cobertura ≥ 80% por repositório, BDD da SAGA, SonarCloud com Quality Gate no CI |
| RT5 | CI/CD | GitHub Actions por repositório, autenticação na AWS via OIDC, deploy automático na `main` |

### Entregáveis do enunciado

- Documentação da arquitetura proposta.
- Script de criação do banco de dados e dos demais recursos.
- Link do GitHub do(s) projeto(s).
- Vídeo de **até 10 minutos** mostrando a documentação, a arquitetura escolhida e o projeto funcionando.

---

## 3. Stack obrigatória e decisões fechadas

| Tema | Decisão (fechada pelo time) |
|---|---|
| Cloud | **AWS** (região padrão `us-east-1`, configurável) |
| IaC | **Terraform** (≥ 1.10), backend remoto S3 com lock nativo (`use_lockfile = true`) |
| Autenticação | **API Gateway (HTTP API) + Lambda em Node.js** (runtime Node.js 24). Usuários em banco próprio no Aurora, senha com bcrypt, **JWT RS256** |
| Aplicação principal | **PHP 8.4.27 + Laravel 13**, em **Docker** no **EKS** (Kubernetes) |
| Worker de processamento | **PHP 8.4.27 + Laravel 13** em repositório próprio, no EKS, com `ffmpeg` na imagem, escalado por **KEDA** pela fila |
| Banco | **Aurora MySQL** (v3, compatível com MySQL 8.0), Serverless v2. **Um database por serviço** no mesmo cluster |
| Arquivos | **Amazon S3** (vídeos e zips) |
| Fila | **Amazon SQS** (todo o processamento passa pela fila) + DLQ |
| Arquitetura de código | **DDD + Clean Architecture** |
| Processamento | **SAGA orquestrada pela aplicação principal** (Laravel), com estado da saga no Aurora e comandos e respostas via SQS |
| Observabilidade | **New Relic** (APM PHP, Kubernetes, Lambda, logs e alertas) |
| Notificação | **SQS → Lambda Node.js → Amazon SES**, com registro de cada envio em **DynamoDB** (partition key = `email`), em repositório próprio |
| Front-end | SPA mínima **React + Vite + TypeScript + Tailwind**, hospedada em **S3 + CloudFront**, em repositório próprio |
| Repositórios | Organização GitHub **[hackathon-fiap-soat](https://github.com/hackathon-fiap-soat)** |
| CI/CD | **GitHub Actions** com OIDC na AWS (sem chaves de acesso fixas). `terraform apply` **via GitHub Actions**; apply local permitido só para testes (§11.5) |
| Documentação | **Primeiro**: Domain Storytelling, ADRs, RFCs, fluxo de deploy, C4, sequência, contratos |

### Decisões técnicas derivadas (o agente deve segui-las e registrá-las em ADR)

1. **Upload direto ao S3 com POST pré-assinado** (`content-length-range` limita o tamanho). O vídeo **não passa
   pelo API Gateway**, que tem limite de payload de 10 MB e timeout de 30 s.
2. **A SAGA começa pelo evento do S3** (`s3:ObjectCreated` → SQS), não por uma chamada do cliente. Se o
   cliente cair depois do upload, o vídeo continua sendo processado.
3. **Contratos de mensagens em JSON puro, com versão** (não usar jobs serializados do Laravel entre
   serviços), porque o worker e as Lambdas precisam ler as mesmas mensagens.
4. **Saídas da infra publicadas no SSM Parameter Store** (`/fiapx/<env>/...`). Os outros repositórios leem dali,
   sem `terraform_remote_state`, o que diminui o acoplamento entre repositórios.
5. **API Gateway → VPC Link → ALB interno.** O ALB e o Target Group são criados pelo Terraform, e o
   `video-api` se registra nele com `TargetGroupBinding` (AWS Load Balancer Controller). Isso evita o
   problema de "ovo e galinha" entre Terraform e Kubernetes.
6. **Uma imagem/pod processa um vídeo por vez.** A concorrência vem do número de pods (KEDA). Durante o
   `ffmpeg`, o worker estende o visibility timeout da mensagem (heartbeat).
7. **UUID v7** gerado no domínio (`ramsey/uuid`, que é biblioteca e não framework) para todas as entidades.
8. **Uma única origem para o usuário:** o CloudFront serve o front-end (`/*` → bucket S3 do site) e
   encaminha `/api/*` para o API Gateway. O navegador não faz chamadas cross-origin para a API (sem CORS).
   Só o upload, que vai direto ao bucket de vídeos, precisa de CORS (origem = domínio do CloudFront).
   Por isso **todas as rotas públicas ficam sob o prefixo `/api`**: `/api/auth/register`,
   `/api/auth/login`, `/api/videos`... No Laravel, isso é o prefixo padrão de `routes/api.php`.
   O CloudFront repassa o caminho sem reescrita, então as rotas do API Gateway também são `/api/...`.
   **Neste documento, toda rota pública é escrita com o prefixo `/api`.**

---

## 4. Repositórios

Prefixo `fiapx-`. Todos na organização **<https://github.com/hackathon-fiap-soat>**. Todos com `main` protegida, PR
obrigatório (aprovação opcional), checks obrigatórios (testes + Sonar) e acesso ao usuário `soat-architecture`.

| # | Repositório | Responsabilidade | Stack |
|---|---|---|---|
| 1 | `fiapx-docs` | Toda a documentação: Domain Storytelling, C4, sequência, ADRs, RFCs, fluxo de deploy, contratos de mensagens (JSON Schema), OpenAPI consolidado, documento de entrega | Markdown + Mermaid + JSON Schema |
| 2 | `fiapx-infra` | VPC, EKS (com add-ons), Aurora, S3, SQS/DLQ, SES, ECR, API Gateway + VPC Link + ALB interno, Secrets, OIDC do GitHub, SSM outputs, ambiente local (docker-compose + LocalStack) | Terraform + Helm |
| 3 | `fiapx-auth` | Lambdas de **register**, **login**, **password** (recuperação e troca de senha) e **authorizer**, rotas `/api/auth/*` no API Gateway, schema `fiapx_auth` | Node.js 24 + Terraform |
| 4 | `fiapx-video-api` | Aplicação principal: gestão de vídeos, URLs pré-assinadas, listagem de status, download, **orquestrador da SAGA**, outbox, consumidores de eventos/respostas, schema `fiapx_video` | PHP 8.4.27 + Laravel 13 + Docker + manifests K8s |
| 5 | `fiapx-video-processor` | Worker: consome `ProcessVideo`/`CleanupArtifacts`, baixa o vídeo, `ffmpeg` → frames → zip → S3, responde à SAGA | PHP 8.4.27 + Laravel 13 + ffmpeg + Docker + manifests K8s + KEDA |
| 6 | `fiapx-notification` | Fila SQS própria → Lambda que envia e-mail via SES e registra cada envio no DynamoDB (chave = e-mail); responde à SAGA | Node.js 24 + DynamoDB + Terraform |
| 7 | `fiapx-web` | Front-end mínimo: cadastro, login, upload (múltiplos vídeos), lista de status e download. Prompt de layout em [`Prompt-layout-web.md`](Prompt-layout-web.md) | React + Vite + TypeScript + Tailwind, S3 + CloudFront |

> Os manifests Kubernetes ficam **no repositório de cada serviço** (`k8s/`). O `fiapx-infra` cria só o cluster e
> os add-ons compartilhados.

---

## 5. Arquitetura

### 5.1 Visão de containers (C4 nível 2)

```mermaid
flowchart LR
  U[Usuário / navegador] -->|HTTPS| CF[CloudFront]
  CF -->|/*| WEB[(S3 site<br/>fiapx-web)]
  CF -->|/api/*| APIGW[API Gateway HTTP API]
  U -->|POST pré-assinado| S3[(S3 fiapx-videos)]

  subgraph Auth[fiapx-auth]
    LREG[Lambda register]
    LLOGIN[Lambda login]
    LAUTHZ[Lambda authorizer]
  end

  APIGW -->|/api/auth/*| LREG & LLOGIN
  APIGW -. valida JWT .-> LAUTHZ
  APIGW -->|/api/videos/* via VPC Link| ALB[ALB interno]

  subgraph EKS[Amazon EKS]
    API[video-api<br/>Laravel 13]
    RELAY[outbox-relay]
    CONS[saga-consumer]
    WRK[video-processor<br/>Laravel 13 + ffmpeg<br/>KEDA 1..10]
  end

  ALB --> API
  LREG & LLOGIN --> AURORA_AUTH[(Aurora MySQL<br/>fiapx_auth)]
  API & RELAY & CONS --> AURORA_VIDEO[(Aurora MySQL<br/>fiapx_video)]

  S3 -->|ObjectCreated| Q_UP[[SQS video-uploaded]]
  Q_UP --> CONS
  RELAY -->|ProcessVideo / CleanupArtifacts| Q_PROC[[SQS processing-commands]]
  RELAY -->|SendNotification| Q_NOTIF[[SQS notification-commands]]
  Q_PROC --> WRK
  WRK <--> S3
  WRK -->|respostas| Q_REPLY[[SQS saga-replies.fifo]]
  Q_NOTIF --> LNOTIF[Lambda notification]
  LNOTIF --> SES[Amazon SES]
  LNOTIF <--> DDB[(DynamoDB<br/>notifications<br/>PK = email)]
  LNOTIF -->|respostas| Q_REPLY
  Q_REPLY --> CONS

  EKS & Auth & LNOTIF -. APM/logs .-> NR[New Relic]
```

Cada fila tem DLQ própria (`*-dlq`), com `maxReceiveCount = 3` (`5` na `video-uploaded`).

### 5.2 Bounded contexts

| Contexto | Serviço | Linguagem ubíqua |
|---|---|---|
| **Identidade** | `fiapx-auth` | Usuário, Credencial, Token de acesso |
| **Gestão de Vídeos** | `fiapx-video-api` | Vídeo, Status do vídeo, Cota de processamento, Saga de processamento, Link de download |
| **Processamento** | `fiapx-video-processor` | Tarefa de processamento, Frame, Pacote de frames (zip), Artefato |
| **Notificação** | `fiapx-notification` | Notificação, Destinatário, Modelo de mensagem |

### 5.3 Ciclo de vida do vídeo

```mermaid
stateDiagram-v2
  [*] --> PENDING_UPLOAD: POST /api/videos
  PENDING_UPLOAD --> UPLOADED: evento S3 (saga iniciada)
  PENDING_UPLOAD --> EXPIRED: upload não feito em 1h
  UPLOADED --> QUEUED: cota reservada + ProcessVideo enviado
  UPLOADED --> FAILED: upload inválido / cota excedida
  QUEUED --> PROCESSING: ProcessingStarted
  PROCESSING --> COMPLETED: VideoProcessed
  PROCESSING --> FAILED: VideoProcessingFailed / timeout (após compensação)
  COMPLETED --> [*]
  FAILED --> [*]
  EXPIRED --> [*]
```

### 5.4 Fluxo principal (sequência)

```mermaid
sequenceDiagram
  autonumber
  actor U as Usuário
  participant GW as API Gateway
  participant A as fiapx-auth
  participant V as video-api
  participant S3
  participant Q as SQS
  participant P as video-processor
  participant N as notification

  U->>GW: POST /api/auth/login (email, senha)
  GW->>A: Lambda login
  A-->>U: JWT (RS256)
  U->>GW: POST /api/videos {filename, size_bytes, content_type} + Bearer
  GW->>A: authorizer (valida JWT)
  GW->>V: request + x-user-id
  V-->>U: 201 {video_id, upload: {url, fields}} (status PENDING_UPLOAD)
  U->>S3: POST multipart (vídeo)
  S3->>Q: ObjectCreated (video-uploaded)
  Q->>V: saga-consumer: inicia saga
  V->>V: valida upload (HeadObject), reserva cota, grava outbox (1 transação)
  V->>Q: ProcessVideo (processing-commands)
  Q->>P: ProcessVideo
  P->>Q: ProcessingStarted (saga-replies)
  P->>S3: baixa vídeo, ffmpeg, zip, sobe results/{id}/frames.zip
  P->>Q: VideoProcessed {zip_key, frame_count}
  Q->>V: conclui saga: COMPLETED, libera cota
  U->>GW: GET /api/videos
  GW->>V: lista com status
  U->>GW: GET /api/videos/{id}/download
  V-->>U: URL pré-assinada do zip (15 min)
  Note over V,N: Em falha: compensação + SendNotification → N → SES → e-mail
```

### 5.5 Rede e segurança

- VPC em 2 AZs: subnets públicas (NAT único para reduzir custo, ALB não), privadas (EKS, Lambdas, Aurora).
- Aurora e ALB **somente** em subnets privadas. O ALB interno só é alcançável pelo VPC Link.
- Lambdas de auth/notification **dentro da VPC** (acesso ao Aurora); VPC endpoints para S3, DynamoDB, SQS,
  Secrets Manager e SSM (o SES sai pelo NAT).
- IAM por serviço com **EKS Pod Identity** (ou IRSA): `video-api` (S3 presign/head/delete, SQS
  send/receive), `video-processor` (S3 get/put/delete em prefixos próprios, SQS), KEDA (SQS GetQueueAttributes).
- Chave privada do JWT no **Secrets Manager** (só a Lambda de login lê). A chave pública fica no SSM (o
  authorizer e o `video-api` leem para validar o token também na aplicação, como defesa em profundidade).
- Bucket S3: Block Public Access, SSE-S3, CORS só para `POST` de upload, lifecycle (`uploads/` expira em
  7 dias; `results/` em 30 dias).

---

## 6. SAGA orquestrada do processamento

O **orquestrador vive no `fiapx-video-api`**: o agregado `ProcessingSaga` guarda o estado no
`fiapx_video.processing_sagas`. Ele reage a mensagens (upload, respostas) e emite comandos pela **outbox**.

### 6.1 Passos

| # | Passo | Participante | Ação | Sucesso | Falha | Compensação |
|---|---|---|---|---|---|---|
| 1 | `ValidateUpload` | video-api (local) | `HeadObject`: existe, tamanho ≤ 500 MB, extensão/MIME permitidos (mp4, avi, mov, mkv, wmv, flv, webm) | segue | `FAILED` (motivo `INVALID_UPLOAD`) | `DeleteUploadedObject` |
| 2 | `ReserveQuota` | video-api (local) | reserva 1 vaga na cota de processamentos simultâneos do usuário (padrão 5) | segue | `FAILED` (motivo `QUOTA_EXCEEDED`) | `ReleaseQuota` |
| 3 | `ProcessVideo` | video-processor | comando via `processing-commands` | `VideoProcessed` | `VideoProcessingFailed` ou **timeout** (padrão 30 min) | `CleanupArtifacts` (apaga `results/{id}/` parcial) |
| 4 | `CompleteVideo` | video-api (local) | `COMPLETED`, grava `zip_key`/`frame_count`, libera cota | — | — | — (**ponto sem retorno**: daqui em diante só há retry) |
| 5 | `NotifyUser` | notification | `SendNotification` (`VIDEO_COMPLETED` opcional, `VIDEO_FAILED` obrigatório) | `NotificationSent` | `NotificationFailed` → retry e DLQ | não compensa (passo após o ponto sem retorno) |

### 6.2 Caminho de falha

```text
Falha no passo N → compensações dos passos < N em ordem inversa
                → vídeo FAILED com failure_reason
                → SendNotification(VIDEO_FAILED)   ← atende RF5
```

Exemplo: o `ffmpeg` falha 3 vezes → o worker responde `VideoProcessingFailed` → a saga envia
`CleanupArtifacts` → recebe `ArtifactsCleaned` → executa `ReleaseQuota` → marca `FAILED` → envia
`SendNotification`.

### 6.3 Estados da saga

`STARTED → UPLOAD_VALIDATED → QUOTA_RESERVED → PROCESSING_REQUESTED → PROCESSING → COMPLETED → NOTIFIED`
e, na falha: `COMPENSATING → COMPENSATED (FAILED) → NOTIFIED`.

### 6.4 Regras de robustez

- **Transactional outbox:** a mudança de estado da saga e o comando a enviar são gravados na **mesma
  transação**. O `outbox-relay` publica e marca `published_at`.
- **Idempotência:** toda mensagem tem `message_id`. O consumidor grava em `processed_messages` na mesma
  transação do efeito. Mensagem repetida vira no-op.
- **Guardas de transição:** o agregado rejeita transições inválidas (por exemplo, `VideoProcessed` em
  saga `COMPENSATING`). A mensagem é descartada com log de warning e não vai para a DLQ.
- **Timeout:** o comando agendado `saga:check-timeouts` (a cada minuto) dispara a compensação das
  sagas `PROCESSING_REQUESTED` ou `PROCESSING` que passaram de `deadline_at` (preenchido em `PROCESSING_REQUESTED` com agora + 30 min e renovado no `ProcessingStarted`).
- **Correlação:** `processing_sagas.correlation_id` (id do evento do S3) é copiado para todos os comandos,
  inclusive os disparados pelo timeout.
- **Limpeza:** `messaging:prune` (diário) apaga mensagens da outbox já publicadas e `processed_messages` com
  mais de 7 dias.
- **Motivo da falha:** banco e mensagens guardam o código (`failure_code`); a API e os e-mails mostram o texto.
- **Contratos:** produtor estrito (schemas com `additionalProperties: false` nos testes do produtor),
  consumidor tolerante (ignora campos desconhecidos). Campo opcional novo é compatível; só mudança
  incompatível gera nova `version`.
- **Worker idempotente:** se `results/{video_id}/frames.zip` já existe, responde `VideoProcessed` sem
  reprocessar.
- **Testes BDD obrigatórios da SAGA:** sucesso; falha no ffmpeg com compensação; timeout; cota excedida;
  upload inválido; mensagem duplicada; resposta fora de ordem.

---

## 7. Mensageria e contratos

### 7.1 Filas (SQS)

| Fila | Tipo | Produtor | Consumidor | Visibility | DLQ |
|---|---|---|---|---|---|
| `fiapx-<env>-video-uploaded` | Standard | S3 (evento) | video-api `saga-consumer` | 60 s | sim (5) |
| `fiapx-<env>-processing-commands` | Standard | video-api `outbox-relay` | video-processor | 300 s + heartbeat | sim (3) |
| `fiapx-<env>-saga-replies.fifo` | FIFO (`MessageGroupId = saga_id`) | processor, notification | video-api `saga-consumer` | 60 s | sim (3) |
| `fiapx-<env>-notification-commands` | Standard (**criada pelo repositório `fiapx-notification`**) | video-api `outbox-relay` | Lambda notification | 60 s | sim (3) |

Alarmes no CloudWatch, integrados ao New Relic: `ApproximateNumberOfMessagesVisible > 0` em qualquer DLQ.

### 7.2 Envelope padrão (todas as mensagens)

```json
{
  "message_id": "0192f1c4-...-uuidv7",
  "type": "ProcessVideo",
  "version": 1,
  "saga_id": "0192f1c4-...",
  "video_id": "0192f1c4-...",
  "correlation_id": "0192f1c4-...",
  "occurred_at": "2026-11-16T12:00:00Z",
  "payload": {}
}
```

### 7.3 Mensagens

| Tipo | Direção | Payload |
|---|---|---|
| `ProcessVideo` | api → processor | `bucket`, `video_key`, `fps` (1), `output_prefix` |
| `CleanupArtifacts` | api → processor | `bucket`, `prefix` |
| `ProcessingStarted` | processor → api | `started_at`, `worker_id` |
| `VideoProcessed` | processor → api | `zip_key`, `frame_count`, `zip_size_bytes`, `duration_ms` |
| `VideoProcessingFailed` | processor → api | `error_code` (`FFMPEG_ERROR`, `NO_FRAMES`, `DOWNLOAD_ERROR`, `UPLOAD_ERROR`), `error_message`, `attempt` |
| `ArtifactsCleaned` | processor → api | `deleted_objects` |
| `SendNotification` | api → notification (vídeo) e auth → notification (senha) | `template` (`VIDEO_FAILED` / `VIDEO_COMPLETED` / `PASSWORD_RESET` / `PASSWORD_CHANGED`), `recipient_email`, `recipient_name`, `video_name` (só templates de vídeo), `reason?`, `action_url` (só `PASSWORD_RESET`). Nos templates de senha, `saga_id` e `video_id` são `null` e não há resposta na `saga-replies.fifo` (ADR-017) |
| `NotificationSent` / `NotificationFailed` | notification → api | `channel`, `provider_message_id?`, `error?` |

O agente deve escrever um **JSON Schema por mensagem** em `fiapx-docs/contracts/` e validar as mensagens
contra esses schemas nos testes de cada serviço (*contract tests*).

---

## 8. Especificação por repositório

### 8.1 `fiapx-docs` (criar PRIMEIRO)

```text
fiapx-docs/
├── README.md                          # índice de toda a documentação
├── 01-contexto/
│   ├── visao-geral.md                 # problema, objetivos, requisitos RF/RT, diagnóstico do projeto base
│   └── linguagem-ubiqua.md            # glossário por bounded context
├── 02-domain-storytelling/
│   ├── README.md                      # notação usada e como abrir no Egon.io
│   ├── ds-01-cadastro-e-login.md
│   ├── ds-02-envio-de-video.md
│   ├── ds-03-processamento-com-sucesso.md
│   ├── ds-04-falha-e-notificacao.md
│   ├── ds-05-consulta-status-e-download.md
│   └── *.egn / *.svg                  # opcional: exportados do Egon.io (o time desenha manualmente)
├── 03-arquitetura/
│   ├── c4-contexto.md                 # Mermaid
│   ├── c4-containers.md
│   ├── c4-componentes-video-api.md
│   ├── sequencias.md                  # login, upload+processamento, falha+compensação, download
│   ├── saga.md                        # passos, estados, compensações, timeouts
│   ├── modelo-de-dados.md             # ER (Mermaid erDiagram) dos dois databases
│   ├── seguranca.md
│   └── escalabilidade-e-resiliencia.md
├── 04-adrs/                           # formato MADR: Contexto, Decisão, Alternativas, Consequências
├── 05-rfcs/                           # formato: Resumo, Motivação, Proposta, Alternativas, Riscos, Decisão
├── 06-deploy/
│   ├── fluxo-de-deploy.md             # pipelines, ordem entre repos, rollback
│   └── ambientes.md                   # local (compose + LocalStack) e prod (AWS), custos e destroy
├── 07-observabilidade/
│   ├── observabilidade.md
│   └── newrelic-dashboard.json
├── contracts/                         # JSON Schema de cada mensagem (§7.3)
├── api/openapi.yaml                   # OpenAPI consolidado (auth + video-api)
└── entrega/
    ├── entrega-fase5.md               # participantes, links, vídeo (→ exportar PDF)
    └── roteiro-video.md               # roteiro de até 10 min
```

**Domain Storytelling** (notação textual, uma história por arquivo, com diagrama Mermaid):
`<nº> <Ator> --<atividade>--> <Objeto de trabalho> --para/com--> <Ator>`. Exemplo para `ds-02`:

```text
1. Usuário  --informa-->  dados do vídeo (nome, tamanho, formato)  --para-->  Plataforma FIAP X
2. Plataforma FIAP X  --cria-->  Vídeo (aguardando envio) e autorização de envio  --para-->  Usuário
3. Usuário  --envia-->  arquivo de vídeo  --para-->  Armazenamento
4. Armazenamento  --avisa-->  chegada do vídeo  --para-->  Plataforma FIAP X
5. Plataforma FIAP X  --valida-->  Vídeo  e  --reserva-->  Cota de processamento
6. Plataforma FIAP X  --coloca-->  pedido de processamento  --na-->  Fila
```

Atores: Usuário, Plataforma FIAP X, Serviço de Identidade, Armazenamento, Fila, Processador,
Serviço de Notificação. Objetos de trabalho: Credencial, Token, Vídeo, Cota, Pedido de processamento,
Frames, Pacote zip, Link de download, E-mail.

**ADRs obrigatórios** (`04-adrs/ADR-NNN-titulo.md`, status `Aceito`):

| ADR | Título |
|---|---|
| 001 | Um repositório por serviço (polyrepo) e comunicação entre repositórios via SSM Parameter Store |
| 002 | AWS como cloud e Terraform como IaC, com backend S3 e lock nativo |
| 003 | DDD + Clean Architecture nos serviços Laravel |
| 004 | Autenticação com API Gateway + Lambda Node.js + Lambda Authorizer e JWT RS256 |
| 005 | Aurora MySQL Serverless v2 com um database por serviço no mesmo cluster |
| 006 | Upload direto ao S3 via POST pré-assinado e início da SAGA pelo evento do S3 |
| 007 | Amazon SQS como mensageria (Standard para comandos, FIFO para respostas, DLQ em todas) |
| 008 | SAGA orquestrada no video-api com transactional outbox e consumidores idempotentes |
| 009 | Worker Laravel no EKS escalado por KEDA (1 vídeo por pod, heartbeat de visibility) |
| 010 | Exposição da API: API Gateway → VPC Link → ALB interno + TargetGroupBinding |
| 011 | Observabilidade com New Relic |
| 012 | CI/CD com GitHub Actions + OIDC e ordem de deploy entre repositórios |
| 013 | Notificação: SQS → Lambda Node.js → SES, com histórico e idempotência no DynamoDB (PK `email`, SK `message_id`) |
| 014 | Front-end React + Vite em S3 + CloudFront, com `/api/*` na mesma origem |
| 015 | Remetente de e-mail: domínio próprio no Route 53 com DKIM/SPF/DMARC e uso do sandbox do SES |
| 016 | `terraform apply` somente via GitHub Actions; apply local apenas para testes (§11.5) |
| 017 | Recuperação e troca de senha no `fiapx-auth`, com e-mail pelo `fiapx-notification` |
| 018 | Orquestração do deploy no GitHub Actions: `deploy-all.yml` e `destroy-all.yml` no `fiapx-infra`, chamando o `deploy.yml` reutilizável de cada repositório |

**RFCs obrigatórias** (`05-rfcs/RFC-NNN-titulo.md`, cada uma com alternativas comparadas em tabela):

| RFC | Tema | Alternativas a comparar |
|---|---|---|
| 001 | Escolha da cloud e da IaC | AWS+Terraform × GCP × Azure × CloudFormation/CDK |
| 002 | Upload de arquivos grandes | via API × S3 pré-assinado (PUT × POST) × multipart |
| 003 | Estratégia da SAGA | orquestrada no Laravel × Step Functions × coreografia SNS/SQS |
| 004 | Autenticação | Lambda própria + Aurora × Cognito × JWT na aplicação |
| 005 | Escala do processamento | KEDA por fila × HPA por CPU × Lambda container × AWS Batch |
| 006 | Mensageria | SQS × SNS+SQS × RabbitMQ (Amazon MQ) × Kafka (MSK) |
| 007 | Banco de dados e cache | Aurora MySQL × RDS MySQL × Aurora PostgreSQL + Redis (**stack recomendada no enunciado**) × DynamoDB. Justificar a escolha do MySQL e a ausência de Redis |
| 008 | Registro de notificações | DynamoDB × tabela no Aurora × apenas logs |
| 009 | Hospedagem do front-end | S3 + CloudFront × Amplify Hosting × container no EKS |
| 010 | Observabilidade | New Relic × Prometheus + Grafana (**recomendado no enunciado**) × ELK × CloudWatch |

**Fluxo de deploy** (`06-deploy/fluxo-de-deploy.md`): ver §11. Deve ter um diagrama Mermaid da ordem entre
repositórios e um da pipeline de cada tipo de repositório.

### 8.2 `fiapx-infra`

```text
fiapx-infra/
├── bootstrap/            # state local, roda 1x: bucket S3 do tfstate (versionado, criptografado) + role OIDC do GitHub
├── modules/
│   ├── network/          # VPC, subnets, NAT, VPC endpoints
│   ├── eks/              # cluster, managed node group, Pod Identity, add-ons
│   ├── eks-addons/       # Helm: aws-load-balancer-controller, metrics-server, keda, newrelic nri-bundle
│   ├── aurora/           # Aurora MySQL Serverless v2, subnet group, SG, secret do master, databases
│   ├── storage/          # bucket S3, CORS, lifecycle, notificação ObjectCreated → SQS (prefixo uploads/)
│   ├── messaging/        # 3 filas compartilhadas (video-uploaded, processing-commands, saga-replies) + DLQs + alarmes
│   │                     #   (a notification-commands é do repositório fiapx-notification, ver §8.6)
│   ├── ses/              # domínio no Route 53 + identidade SES (Easy DKIM, SPF, DMARC, MAIL FROM) + configuration set (§8.6.4)
│   ├── ecr/              # fiapx-video-api, fiapx-video-processor (scan on push, lifecycle)
│   ├── edge/             # API Gateway HTTP API, stage, VPC Link, ALB interno, Target Group, logs de acesso
│   ├── web-hosting/      # bucket do site (privado, OAC) + CloudFront: /* → site, /api/* → API Gateway
│   │                     #   o domínio do CloudFront alimenta o CORS do bucket de vídeos
│   └── ssm-outputs/      # publica tudo em /fiapx/<env>/...
├── envs/prod/            # main.tf, backend.tf, variables.tf, terraform.tfvars.example
├── local/
│   ├── docker-compose.yml   # mysql:8.0, localstack 4.14.0 (s3, sqs, ses, ssm, secretsmanager, dynamodb), mailpit
│   └── init/                # scripts que criam bucket/filas/databases no LocalStack/MySQL
├── sql/                     # create-databases.sql (fiapx_auth, fiapx_video, usuários com GRANT mínimo)
└── .github/workflows/       # terraform.yml
```

Parâmetros SSM publicados (exemplos): `/fiapx/prod/vpc/private_subnet_ids`, `/eks/cluster_name`,
`/aurora/endpoint`, `/aurora/secret_arn`, `/s3/videos_bucket`, `/sqs/<fila>/url`, `/sqs/<fila>/arn`,
`/apigw/api_id`, `/apigw/vpc_link_id`, `/alb/target_group_arn`, `/ecr/<repo>/url`, `/ses/from_address`,
`/ses/configuration_set`, `/web/bucket`, `/web/cloudfront_distribution_id`, `/web/url`.
Publicado pelo `fiapx-notification` (lido pelo `video-api`): `/fiapx/prod/sqs/notification-commands/url`.
Catálogo completo (chaves, segredos, quem publica e quem lê): `fiapx-docs/06-deploy/parametros-ssm.md`.

### 8.3 `fiapx-auth` (Node.js 24)

```text
fiapx-auth/
├── src/
│   ├── domain/           # User (entidade), Email e Password (VOs), regras de senha
│   ├── application/      # RegisterUser, AuthenticateUser, VerifyToken (use cases) + ports
│   ├── infrastructure/   # MysqlUserRepository (mysql2), BcryptHasher, JwtRs256Signer, SecretsProvider
│   └── handlers/         # register.js, login.js, authorizer.js (adapters de entrada da Lambda)
├── migrations/           # 001_create_users.sql (schema fiapx_auth)
├── tests/                # jest: unit + integração (MySQL do compose)
├── infra/                # Terraform: lambdas, roles, rotas POST /api/auth/register e /api/auth/login, authorizer
└── .github/workflows/
```

- `POST /api/auth/register` `{name, email, password}` → 201. E-mail único, bcrypt custo 12. **Política de senha**
  (cadastro, redefinição e troca): 8 a 72 caracteres, com pelo menos uma letra maiúscula, um número e um símbolo.
- **Recuperação e troca de senha** (Lambda `password`, ADR-017):
  - `POST /api/auth/password/forgot` `{email}` → sempre 202. Gera token aleatório de 256 bits (só o hash SHA-256 vai
    para `password_reset_tokens`), válido por 30 min e de uso único; invalida os anteriores; publica
    `SendNotification` `PASSWORD_RESET` com o link `<web_url>/redefinir-senha?token=...`. No máximo 1 e-mail a cada
    2 min por usuário.
  - `POST /api/auth/password/reset/verify` `{token}` → 200 `{email_masked, expires_at}` ou 422 genérico.
  - `POST /api/auth/password/reset` `{token, password}` → 200 com JWT (troca e já entra) + `PASSWORD_CHANGED`.
  - `PUT /api/auth/password` `{current_password, new_password}` (com authorizer) → 204 + `PASSWORD_CHANGED`.
  - O token vai sempre no corpo (nunca na URL da API). JWTs emitidos antes da troca valem até expirar (≤ 1 h).
- `POST /api/auth/login` `{email, password}` → `{access_token, token_type: "Bearer", expires_in: 3600}`.
  Claims: `sub` (user_id), `email`, `name`, `iss: fiapx-auth`, `aud: fiapx-api`, `exp`.
- **Authorizer** (REQUEST, payload 2.0, respostas simples, cache de 300 s): valida assinatura RS256, `iss`,
  `aud` e `exp`, e repassa `user_id`, `email` e `name` no contexto. O API Gateway injeta esses valores como
  headers `x-user-id`, `x-user-email` e `x-user-name` para o `video-api`.
- Respostas de erro genéricas (não revelar se o e-mail existe): cadastro com e-mail repetido devolve o mesmo
  422 genérico ("Não foi possível concluir o cadastro"). Rate limit no stage do API Gateway.
- O authorizer com respostas simples devolve **403** para token inválido ou expirado e **401** quando falta o
  header; o front trata os dois como sessão expirada.

### 8.4 `fiapx-video-api` (PHP 8.4.27 + Laravel 13) — aplicação principal

Estrutura DDD + Clean Architecture (mesmo padrão do `tech-challenge-application`, com as regras de ouro:
**Domain** sem framework, **Application** só depende de interfaces, **Infrastructure** implementa,
**Presentation** só converte HTTP ↔ DTO; handler global de exceções em `bootstrap/app.php`, sem try/catch
em controller/use case):

```text
app/
├── Domain/
│   ├── Video/
│   │   ├── Entities/Video.php                       # agregado: create(), markUploaded(), markQueued(), markProcessing(), complete(), fail(), expire()
│   │   ├── ValueObjects/{VideoId,VideoStatus,StorageKey,FileName,FileSize,VideoFormat,FailureReason}.php
│   │   ├── Events/{VideoCreated,VideoCompleted,VideoFailed}.php
│   │   └── Interfaces/VideoRepositoryInterface.php
│   ├── Saga/
│   │   ├── Entities/ProcessingSaga.php              # máquina de estados + compensações (puro PHP)
│   │   ├── ValueObjects/{SagaState,SagaStep,Deadline}.php
│   │   └── Interfaces/ProcessingSagaRepositoryInterface.php
│   ├── Quota/
│   │   ├── Entities/ProcessingQuota.php             # reserve(), release()
│   │   └── Interfaces/ProcessingQuotaRepositoryInterface.php
│   └── Shared/Interfaces/{Clock,IdGenerator}.php
├── Application/
│   ├── Video/UseCases/{RequestVideoUpload,ListUserVideos,ShowVideo,GetDownloadLink}UseCase.php
│   ├── Video/DTOs/...
│   ├── Saga/UseCases/{StartProcessingSaga,HandleSagaReply,CheckSagaTimeouts}UseCase.php
│   ├── Saga/Ports/{CommandBus,ObjectStorage,UserDirectory}.php    # saídas (implementadas na Infrastructure)
│   └── Shared/{TransactionManager,MessageDeduplicator}.php
├── Infrastructure/
│   ├── Persistence/Eloquent/{Models,Repositories}/
│   ├── Messaging/{SqsClientFactory,OutboxCommandBus,OutboxRelay,SqsConsumer,MessageEnvelope,Handlers/*}.php
│   ├── Storage/S3ObjectStorage.php                # presigned POST, HeadObject, presigned GET, delete
│   └── Auth/GatewayUserResolver.php               # lê x-user-* e revalida JWT com a chave pública
├── Presentation/
│   ├── Http/Controllers/{VideoController,HealthController}.php
│   ├── Http/Requests/{RequestVideoUpload,ListVideos}Request.php
│   ├── Http/Resources/VideoResource.php
│   └── Console/Commands/{OutboxRelayCommand,SagaConsumeCommand,SagaCheckTimeoutsCommand,ExpirePendingUploadsCommand}.php
└── Providers/RepositoryServiceProvider.php
```

**Endpoints** (todos atrás do authorizer, exceto health):

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/api/videos` | `{filename, size_bytes, content_type}` → 201 `{id, status: PENDING_UPLOAD, upload: {url, fields, expires_at}}` |
| `GET` | `/api/videos` | lista paginada do usuário (`?status=&page=&per_page=`), ordenada por `created_at desc` |
| `GET` | `/api/videos/{id}` | detalhe com status, `frame_count`, `failure_reason`, timestamps (404 se não for do usuário) |
| `GET` | `/api/videos/{id}/download` | 200 `{url, expires_at}` se `COMPLETED`; 409 caso contrário |
| `GET` | `/api/health/live`, `/api/health/ready` | probes do Kubernetes e smoke test pelo gateway (o ready testa DB e SQS); rota sem authorizer |

**Processos no Kubernetes** (mesma imagem, comandos diferentes):

| Deployment | Comando | Escala |
|---|---|---|
| `video-api-web` | php-fpm + nginx (ou FrankenPHP/Octane) | HPA CPU 70%, 2–6 réplicas |
| `video-api-outbox-relay` | `php artisan outbox:relay` | 1–2 (relay com `SELECT ... FOR UPDATE SKIP LOCKED`) |
| `video-api-saga-consumer` | `php artisan saga:consume` (long polling nas filas `video-uploaded` e `saga-replies`) | KEDA 1–5 |
| CronJob | `php artisan schedule:run` (timeouts, expiração de uploads pendentes, `messaging:prune` diário) | 1/min |
| Job (pré-deploy) | `php artisan migrate --force` | por deploy |

`k8s/`: `namespace`, `serviceaccount` (Pod Identity), `configmap`, `externalsecret` ou secret gerado no CI a
partir do Secrets Manager, `deployment-*`, `service`, `targetgroupbinding`, `hpa`, `scaledobject`,
`cronjob`, `job-migrate`, `pdb`. Usar **Kustomize** (`base/` + `overlays/prod`).

Dockerfile multi-stage: `composer install --no-dev` em stage separado → imagem final `php:8.4.27-fpm-alpine`
com extensões `pdo_mysql`, `opcache`, `intl`, agente New Relic PHP, usuário não-root e `HEALTHCHECK`.

### 8.5 `fiapx-video-processor` (PHP 8.4.27 + Laravel 13 + ffmpeg)

```text
app/
├── Domain/Processing/
│   ├── Entities/ProcessingJob.php                 # start(), finish(frames, zip), fail(reason)
│   ├── ValueObjects/{FramesPerSecond,StorageLocation,FrameSet,ProcessingError}.php
│   └── Interfaces/{FrameExtractor,FrameArchiver,ObjectStorage,ReplyPublisher}.php
├── Application/Processing/UseCases/{ProcessVideoUseCase,CleanupArtifactsUseCase}.php
├── Infrastructure/
│   ├── Media/FfmpegFrameExtractor.php             # Symfony Process; timeout; parse de erros
│   ├── Media/ZipFrameArchiver.php                 # ZipArchive, gravação em streaming
│   ├── Storage/S3ObjectStorage.php                # download em stream para /work, multipart upload
│   └── Messaging/{SqsCommandConsumer,SqsReplyPublisher,VisibilityHeartbeat}.php
└── Presentation/Console/Commands/ConsumeCommandsCommand.php   # php artisan processor:consume
```

- Um pod processa **uma mensagem por vez**: `ReceiveMessage` (long polling 20 s) → use case → `DeleteMessage`
  **só depois** de subir o zip e publicar a resposta.
- **Heartbeat:** enquanto o `ffmpeg` roda, chamar `ChangeMessageVisibility` a cada 60 s (+300 s).
- Diretório de trabalho `/work` em `emptyDir` com `sizeLimit` (ex.: 10Gi). Limpar sempre no `finally`.
- **Graceful shutdown:** tratar `SIGTERM` (`pcntl`), terminar o vídeo atual e não pegar novas mensagens;
  `terminationGracePeriodSeconds` maior que o tempo máximo de processamento esperado.
- Falha **definitiva** (vídeo corrompido, sem frames): responde `VideoProcessingFailed` na hora e apaga a
  mensagem. Falha **transitória** (S3 ou rede): não apaga, a mensagem volta para a fila e, depois de 3
  tentativas, vai para a DLQ. Nesse caso o timeout da saga cobre a compensação.
- KEDA `ScaledObject` (`aws-sqs-queue`, `queueLength: 1`, `minReplicaCount: 1`, `maxReplicaCount: 10`).
- Sem banco próprio (stateless). Idempotência pela chave determinística `results/{video_id}/frames.zip`.
- Dockerfile: `php:8.4.27-cli-alpine` + `ffmpeg` + extensões `zip`, `pcntl`; usuário não-root.

### 8.6 `fiapx-notification` (Node.js 24 + SQS + SES + DynamoDB)

Serviço autônomo, dono da **própria fila**, da **própria Lambda** e da **própria tabela NoSQL**.

```text
fiapx-notification/
├── src/
│   ├── domain/           # Notification (entidade), Recipient/Email (VO), NotificationStatus, Template
│   ├── application/      # SendNotificationUseCase + ports (EmailSender, NotificationRepository, ReplyPublisher)
│   ├── infrastructure/   # SesEmailSender, SmtpEmailSender (Mailpit local), DynamoNotificationRepository, SqsReplyPublisher
│   ├── templates/        # video-failed, video-completed, password-reset, password-changed (.html e .txt, pt-BR)
│   └── handlers/         # sqs-handler.js (entrada), ses-events-handler.js (opcional, §8.6.4)
├── tests/                # jest: unit + integração (DynamoDB/SQS/SES no LocalStack)
├── infra/                # Terraform: SQS notification-commands + DLQ, Lambda, event source mapping, DynamoDB, IAM, alarmes
└── .github/workflows/
```

#### 8.6.1 Fluxo

```mermaid
sequenceDiagram
  participant V as video-api (outbox-relay)
  participant Q as SQS notification-commands
  participant L as Lambda notification
  participant D as DynamoDB notifications
  participant S as Amazon SES
  participant R as SQS saga-replies.fifo
  V->>Q: SendNotification
  Q->>L: lote (batch size 10)
  L->>D: PutItem status=PENDING (condicional: ainda não enviado)
  alt já enviado (mensagem duplicada)
    L->>R: NotificationSent (idempotente, sem reenviar o e-mail)
  else novo
    L->>S: SendEmail (configuration set)
    S-->>L: ses_message_id
    L->>D: UpdateItem status=SENT, ses_message_id, sent_at
    L->>R: NotificationSent
  end
  Note over L,D: Erro no SES: status=FAILED, attempt+1, item volta para a fila<br/>(ReportBatchItemFailures). Na 3ª tentativa: NotificationFailed e a mensagem vai para a DLQ
```

#### 8.6.2 Tabela DynamoDB `fiapx-<env>-notifications`

A **partition key é o e-mail do destinatário**, como o time pediu. Para guardar **o histórico de todos os
envios** de um mesmo e-mail (e não sobrescrever o último), a tabela tem uma sort key:

| Atributo | Tipo | Papel |
|---|---|---|
| `email` | S | **Partition key**: destinatário (normalizado em minúsculas) |
| `message_id` | S | **Sort key**: id do `SendNotification`. Garante a idempotência com `attribute_not_exists` |
| `created_at` | S (ISO-8601) | Sort key do **LSI `email-created_at-index`**: histórico em ordem cronológica por e-mail |
| `status` | S | `PENDING` · `SENT` · `FAILED` · `DELIVERED` · `BOUNCED` · `COMPLAINED` |
| `template` | S | `VIDEO_FAILED` · `VIDEO_COMPLETED` |
| `subject` | S | assunto enviado |
| `video_id`, `saga_id`, `correlation_id` | S | rastreabilidade com a SAGA |
| `ses_message_id` | S | id retornado pelo SES |
| `attempts` | N | tentativas de envio |
| `last_error` | S | última mensagem de erro |
| `sent_at`, `updated_at` | S | timestamps |
| `expires_at` | N | **TTL** (epoch; 90 dias) |

Consultas suportadas: "todos os envios para o e-mail X" (`Query email = X` no LSI, mais recentes primeiro)
e "esse comando já foi enviado?" (`GetItem email + message_id`). Billing `PAY_PER_REQUEST`, PITR ligado,
criptografia padrão.

#### 8.6.3 Regras

- Event source mapping com `batch_size = 10`, `function_response_types = ["ReportBatchItemFailures"]`,
  `maxReceiveCount = 3` na fila e DLQ `notification-commands-dlq` com alarme.
- Condição do `PutItem`: `attribute_not_exists(message_id) OR #status = :failed` (só reenvia o que falhou).
- Validar o payload contra o JSON Schema `SendNotification` (`fiapx-docs/contracts`). Payload inválido é
  registrado como `FAILED` e não é reenviado.
- Templates em pt-BR, com nome do vídeo, motivo da falha legível (`FFMPEG_ERROR` → "O arquivo de vídeo
  está corrompido ou em um formato que não conseguimos ler") e link para o front-end (`/web/url`).
- Local: `EMAIL_DRIVER=smtp` envia para o **Mailpit**. AWS: `EMAIL_DRIVER=ses`.

#### 8.6.4 Remetente de e-mail (SES)

**Decisão do time: domínio `hackfiapf5`, registrado no Route 53 e verificado no SES pelo Terraform (opção A).**

- Domínio: **`hackfiapf5.click`** (extensão mais barata no Route 53). Antes de registrar, o agente confere
  a disponibilidade (`aws route53domains check-domain-availability`). Se não estiver livre, tenta nesta
  ordem `hackfiapf5.link` e `hackfiapf5.com`, e registra no ADR-015 qual foi usado.
- Remetente: **`nao-responda@hackfiapf5.click`** (nome de exibição "FIAP X").
- MAIL FROM personalizado: `mail.hackfiapf5.click`. DMARC: `v=DMARC1; p=quarantine; rua=mailto:dmarc@hackfiapf5.click`.
- O registro do domínio é **manual e feito uma única vez pelo time** (cobrança anual, contato do titular).
  A hosted zone, os registros DKIM/SPF/DMARC/MAIL FROM e a identidade SES ficam no Terraform
  (`fiapx-infra/modules/ses`).

Alternativas avaliadas:

| Opção | Custo | Prós | Contras |
|---|---|---|---|
| **A. Domínio novo no Route 53** (`hackfiapf5.click`), remetente `nao-responda@hackfiapf5.click` **(escolhida)** | ~US$ 3–15/ano + US$ 0,50/mês da hosted zone | Easy DKIM + SPF + DMARC alinhados, criados 100% pelo Terraform; e-mails não caem em spam; pode-se pedir saída do sandbox | Precisa registrar o domínio (uma vez, manual ou via Terraform) |
| B. Subdomínio de um domínio que o time já tenha (ex.: `fiapx.<dominio-existente>`) | zero | mesmos prós da A | depende de acesso ao DNS desse domínio |
| C. Gmail dedicado do projeto (ex.: uma conta criada só para o hackathon), verificado como *email identity* | zero | rápido para começar | sem DKIM do domínio: tende a cair em spam ou ser rejeitado (DMARC do Gmail); não serve para sair do sandbox |

**Sandbox do SES (toda conta nova começa nele):** só envia para **destinatários verificados**, até 200
e-mails/dia. Para o hackathon isso basta: verificar os e-mails dos integrantes e as contas de demonstração.
Pedir saída do sandbox é opcional (exige domínio, opção A ou B).

**Testes automatizados e demonstração de falha:** usar o **mailbox simulator do SES**, que funciona até
no sandbox e sem verificação:
`success@simulator.amazonses.com`, `bounce@simulator.amazonses.com`, `complaint@simulator.amazonses.com`.

**Opcional (bom para a apresentação):** configuration set do SES com destino de eventos (SNS ou
EventBridge) → `ses-events-handler` atualiza o item no DynamoDB para `DELIVERED`, `BOUNCED` ou `COMPLAINED`.

### 8.7 `fiapx-web` (React + Vite + TypeScript + Tailwind)

- Front-end mínimo e funcional. O layout foi gerado pelo time no Google Stitch e está versionado em
  `fiapx-web/stitch_fiap_x_video_processor_front_end/` (HTML + print por tela e `DESIGN.md`). O agente o
  implementa em React e o integra aos contratos reais. O escopo de cada tela (editar perfil fica fora,
  exceto a seção de senha) e os elementos do painel sem suporte na API estão listados no README do
  `fiapx-web`.
- Telas: **Cadastro**, **Login**, **Meus vídeos** (upload múltiplo com barra de progresso + tabela de
  status com atualização automática), **Download** do zip, **Recuperar senha** (`/recuperar-senha`),
  **Criar nova senha** (`/redefinir-senha?token=`) e **Trocar senha** logado (`/conta/senha`) (ADR-017).
- `VITE_API_BASE_URL=/api` (mesma origem via CloudFront). O token fica em memória + `sessionStorage`;
  401 ou 403 → volta para o login.
- Upload: `POST /api/videos` → `POST` multipart no S3 com os `fields` recebidos (o arquivo deve ser o
  **último** campo), com progresso via `XMLHttpRequest` (o `fetch` não informa progresso de upload).
- Modo **mock** (MSW) para desenvolver e demonstrar o layout sem back-end.
- Testes: Vitest + Testing Library (cobertura ≥ 80%) e um teste E2E com Playwright (login → upload → status).
- Deploy: `npm run build` → `aws s3 sync dist/` para o bucket `/web/bucket` → invalidação do CloudFront.
  O bucket e o CloudFront são criados pelo `fiapx-infra` (módulo `web-hosting`).

---

## 9. Banco de dados

Um cluster **Aurora MySQL Serverless v2** (mín. 0,5 ACU; máx. 4 ACU), com **databases e usuários
separados por serviço**. Nenhum serviço acessa o database de outro.

### 9.1 `fiapx_auth` (dono: `fiapx-auth`)

```sql
CREATE TABLE users (
  id             CHAR(36)     NOT NULL PRIMARY KEY,
  name           VARCHAR(120) NOT NULL,
  email          VARCHAR(180) NOT NULL,
  password_hash  VARCHAR(255) NOT NULL,
  created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE password_reset_tokens (
  id          CHAR(36)  NOT NULL PRIMARY KEY,
  user_id     CHAR(36)  NOT NULL,
  token_hash  CHAR(64)  NOT NULL,                  -- SHA-256 do token; o token em si nunca é gravado
  expires_at  TIMESTAMP NOT NULL,                  -- criação + 30 min
  used_at     TIMESTAMP NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_reset_token_hash (token_hash),
  KEY idx_reset_user_created (user_id, created_at),
  CONSTRAINT fk_reset_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

### 9.2 `fiapx_video` (dono: `fiapx-video-api`)

```sql
CREATE TABLE videos (
  id              CHAR(36)     NOT NULL PRIMARY KEY,
  user_id         CHAR(36)     NOT NULL,           -- referência lógica (outro serviço), sem FK
  user_email      VARCHAR(180) NOT NULL,           -- snapshot do token, usado na notificação
  user_name       VARCHAR(120) NOT NULL,
  original_name   VARCHAR(255) NOT NULL,
  content_type    VARCHAR(100) NOT NULL,
  size_bytes      BIGINT UNSIGNED NOT NULL,
  video_key       VARCHAR(512) NOT NULL,
  zip_key         VARCHAR(512) NULL,
  frame_count     INT UNSIGNED NULL,
  status          VARCHAR(20)  NOT NULL,           -- PENDING_UPLOAD|UPLOADED|QUEUED|PROCESSING|COMPLETED|FAILED|EXPIRED
  failure_code    VARCHAR(40)  NULL,             -- código (FFMPEG_ERROR...); o texto legível é derivado
  failure_reason  VARCHAR(255) NULL,
  created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_videos_user_created (user_id, created_at),
  KEY idx_videos_status (status)
);

CREATE TABLE processing_sagas (
  id            CHAR(36)    NOT NULL PRIMARY KEY,
  video_id      CHAR(36)    NOT NULL,
  correlation_id CHAR(36)   NOT NULL,              -- id do evento S3 que iniciou a saga
  state         VARCHAR(30) NOT NULL,
  current_step  VARCHAR(30) NOT NULL,
  deadline_at   TIMESTAMP   NULL,
  attempts      TINYINT UNSIGNED NOT NULL DEFAULT 0,
  history       JSON        NOT NULL,              -- [{step, state, at, detail}]
  version       INT UNSIGNED NOT NULL DEFAULT 0,   -- lock otimista
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_sagas_video (video_id),
  KEY idx_sagas_state_deadline (state, deadline_at),
  CONSTRAINT fk_sagas_video FOREIGN KEY (video_id) REFERENCES videos(id)
);

CREATE TABLE processing_quotas (
  user_id        CHAR(36) NOT NULL PRIMARY KEY,
  in_progress    INT UNSIGNED NOT NULL DEFAULT 0,
  max_parallel   INT UNSIGNED NOT NULL DEFAULT 5,
  updated_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE outbox_messages (
  id            CHAR(36)     NOT NULL PRIMARY KEY,   -- = message_id
  destination   VARCHAR(60)  NOT NULL,               -- processing-commands | notification-commands
  type          VARCHAR(60)  NOT NULL,
  payload       JSON         NOT NULL,               -- envelope completo
  attempts      TINYINT UNSIGNED NOT NULL DEFAULT 0,
  published_at  TIMESTAMP    NULL,
  created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_outbox_pending (published_at, created_at)
);

CREATE TABLE processed_messages (
  message_id    CHAR(36)  NOT NULL PRIMARY KEY,
  type          VARCHAR(60) NOT NULL,
  processed_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### 9.3 NoSQL — DynamoDB `fiapx-<env>-notifications` (dono: `fiapx-notification`)

Modelagem em §8.6.2, criada pelo Terraform do `fiapx-notification/infra`.

**Script de criação** (entregável): `fiapx-infra/sql/create-databases.sql` cria os databases e os usuários
com privilégios mínimos. Cada serviço versiona as próprias migrations: Laravel em `database/migrations` e
Node em `migrations/*.sql`. Também deve exportar um `schema.sql` consolidado para a documentação
(`fiapx-docs/03-arquitetura/modelo-de-dados.md` com `erDiagram`).

---

## 10. Observabilidade

| Camada | Instrumentação |
|---|---|
| EKS | `nri-bundle` (Helm) no `fiapx-infra`: infraestrutura, eventos e logs do cluster |
| video-api / processor | agente **New Relic PHP** na imagem. Logs JSON (Monolog `JsonFormatter`) com `correlation_id`, `video_id`, `saga_id` e `user_id` |
| Lambdas | layer New Relic para Node.js + logs JSON |
| SQS / Aurora / S3 | integração AWS ↔ New Relic (CloudWatch Metric Streams) |

**Eventos customizados:** `VideoSagaTransition` (de, para, passo, duração) e `VideoProcessed` (duração,
frames, tamanho).

**Dashboard** (`fiapx-docs/07-observabilidade/newrelic-dashboard.json`): vídeos por status (hoje),
throughput de uploads, tempo de processamento p50/p95, taxa de falha, profundidade de cada fila e das
DLQs, réplicas do worker ao longo do tempo, latência e erros do API Gateway e do `video-api`, sagas
presas (`PROCESSING` com deadline vencido).

**Alertas:** mensagem em DLQ > 0; taxa de falha > 10% em 15 min; fila `processing-commands` com mais de 50
mensagens por 10 min; erro 5xx > 2%; sagas vencidas > 0.

---

## 11. CI/CD e fluxo de deploy

### 11.1 Princípios

- GitHub Actions com **OIDC → IAM Role por repositório** (criadas no `bootstrap` do `fiapx-infra`), sem
  access keys.
- `main` protegida: PR obrigatório (aprovação **opcional**: qualquer integrante, inclusive o autor, pode fazer o
  merge — decisão do time), checks obrigatórios (lint, testes, cobertura ≥ 80%, Quality Gate do SonarCloud).
- Imagens com tag = SHA do commit, scan com **Trivy** (falha em CRITICAL).
- Deploy em produção só na `main`, com **GitHub Environment `prod`** (aprovação manual opcional no
  `terraform apply`).

### 11.2 Pipelines por tipo de repositório

| Repositório | PR | Merge na `main` |
|---|---|---|
| `fiapx-docs` | markdownlint, validação dos JSON Schemas, lint do OpenAPI (Spectral) | publica (GitHub Pages opcional) |
| `fiapx-infra` | `fmt -check`, `validate`, `tflint`, `checkov`, `plan` comentado no PR | `apply` (environment `prod`) |
| `fiapx-auth` / `fiapx-notification` | eslint, jest (cov ≥ 80%), Sonar, `terraform plan` | build do zip → `terraform apply` → smoke test (`/api/auth/login`; na notification, envio para `success@simulator.amazonses.com` e conferência do item no DynamoDB) |
| `fiapx-web` | eslint, vitest (cov ≥ 80%), Sonar, build | build → `s3 sync` → invalidação do CloudFront → Playwright smoke na URL pública |
| `fiapx-video-api` | pint, phpstan (nível 6+), phpunit (cov ≥ 80%, MySQL como service container), behat (SAGA), Sonar, build + Trivy | push no ECR → Job `migrate` → `kustomize edit set image` → `kubectl apply -k` → `rollout status` → smoke test (`/api/health/ready` via gateway) |
| `fiapx-video-processor` | pint, phpstan, phpunit (inclui integração com `ffmpeg` real e um vídeo de 3 s em `tests/fixtures`), Sonar, build + Trivy | push no ECR → `kustomize edit set image` → `kubectl apply -k` → `rollout status` |

### 11.3 Ordem de deploy (primeira subida)

```mermaid
flowchart TD
  B[fiapx-infra/bootstrap<br/>state bucket + OIDC roles<br/>manual, 1x] --> I[fiapx-infra envs/prod<br/>VPC, EKS, Aurora, S3, SQS, SES, ECR, API GW, SSM]
  I --> SQL[create-databases.sql<br/>Job no cluster ou passo do pipeline]
  SQL --> AUTH[fiapx-auth<br/>migrations + lambdas + rotas /auth + authorizer]
  SQL --> API[fiapx-video-api<br/>migrate + deploy + TargetGroupBinding + rotas /api/videos]
  AUTH --> API
  I --> PROC[fiapx-video-processor<br/>deploy + ScaledObject]
  I --> NOTIF[fiapx-notification<br/>SQS + lambda + DynamoDB<br/>publica URL da fila no SSM]
  NOTIF --> API
  NOTIF --> AUTH
  I --> WEB[fiapx-web<br/>build + s3 sync + invalidação]
  API --> E2E[smoke test ponta a ponta<br/>register → login → upload → COMPLETED → download]
  PROC --> E2E
  NOTIF --> E2E
  WEB --> E2E
```

Depois da primeira subida, cada repositório faz deploy independente. Mudanças incompatíveis em contratos
devem subir uma nova `version` no envelope, com os consumidores aceitando as duas versões durante a
transição.

**Rollback:** aplicação → `kubectl rollout undo` (ou reverter o PR, que reimplanta a imagem anterior);
Lambdas → reverter o PR (alias/versão anterior); infra → reverter o PR + `apply`.

### 11.4 Custos

EKS (~US$ 73/mês o control plane), NAT Gateway e Aurora são os itens mais caros. Documentar em
`06-deploy/ambientes.md` o procedimento `terraform destroy` para manter o ambiente desligado fora das
demonstrações. Desenvolvimento e testes rodam **localmente** com `fiapx-infra/local/docker-compose.yml`.

### 11.5 Política de `terraform apply`

| Onde | Quando | Como |
|---|---|---|
| **GitHub Actions (padrão)** | todo merge na `main` de `fiapx-infra`, `fiapx-auth`, `fiapx-notification` (e o `infra/` de qualquer repo) | job `apply` no environment `prod`, role OIDC do repositório, mesmo backend S3 com lock nativo. O PR sempre roda `plan` e comenta o resultado |
| **Subir tudo** | antes das demonstrações | workflow manual `deploy-all.yml` no `fiapx-infra` (`confirm = "deploy-prod"`): infra e depois o `deploy.yml` de cada repositório na ordem, com smoke ponta a ponta (ADR-018) |
| **Destroy** | fora das demonstrações | workflow manual `destroy-all.yml` no `fiapx-infra` (`confirm = "destroy-prod"`): ordem inversa, infra por último (ADR-018) |
| **Local — LocalStack** | desenvolvimento e testes do Terraform a qualquer momento | `tflocal` / provider apontando para `http://localhost:4566`, state local em `.terraform-local/` (no `.gitignore`) |
| **Local — AWS real** | **só quando necessário para testar** algo que o LocalStack não cobre (ex.: EKS, SES de verdade) | perfil AWS SSO do integrante, **mesmo backend remoto** (o lock evita colisão com o CI). Registrar no PR o que foi aplicado; o código precisa estar no PR antes ou logo depois, para o próximo apply do CI não reverter |

Bloqueios: o workflow `apply` nunca roda em PR de fork; `prevent_destroy` em Aurora, bucket de vídeos e
tabela DynamoDB; o `destroy-all.yml` desliga essas proteções por variável explícita. Todo merge na `main`
de um serviço faz deploy dele; com o ambiente destruído, esse deploy falha ao ler o SSM (decisão do time).

---

## 12. Plano de execução para o agente

Cada etapa termina com **Definition of Done (DoD)**. Os pontos marcados com 🛑 exigem **aprovação humana**
antes de continuar.

### Etapa 0 — Repositórios e padrões

- Criar os 7 repositórios na organização `hackathon-fiap-soat` (ou pastas locais, se não houver permissão no GitHub), com README inicial,
  `.editorconfig`, `.gitignore`, licença, template de PR, `CODEOWNERS` e proteção da `main`.
- **DoD:** repositórios criados e listados no `fiapx-docs/README.md`.

### Etapa 1 — Documentação (fiapx-docs) 🛑

- Escrever **tudo** do §8.1: visão geral, linguagem ubíqua, 6 Domain Storytellings, C4 (contexto,
  containers, componentes), sequências, SAGA, modelo de dados, segurança, escalabilidade, **18 ADRs**,
  **10 RFCs**, fluxo de deploy, ambientes, observabilidade, JSON Schemas dos contratos, OpenAPI, roteiro do
  vídeo e rascunho do documento de entrega.
- **DoD:** lint verde e diagramas Mermaid renderizando. **Parar e pedir revisão do time** antes de escrever
  código.

### Etapa 2 — Ambiente local (fiapx-infra/local)

- docker-compose com MySQL 8.0, LocalStack (S3, SQS, SES, SSM, Secrets Manager) e Mailpit; scripts de
  init criando bucket, filas, DLQs, notificação S3 → SQS e databases.
- **DoD:** `docker compose up` sobe tudo e um script de verificação lista os recursos criados.
- ✅ Concluída em 2026-11-16 (fiapx-infra#2, fiapx-docs#5): `docker compose up -d --wait` + `./scripts/verificar.sh`,
  também no CI (`ambiente-local`). LocalStack fixado em 4.14.0 (última Community sem token).

### Etapa 3 — fiapx-auth

- Domínio, use cases, handlers (register, login, password, authorizer), migrations (`users`,
  `password_reset_tokens`), testes (≥ 80%), contract test do `SendNotification` de senha, Terraform das Lambdas
  e das rotas.
- **DoD:** testes verdes; login localmente devolve um JWT válido, e o authorizer aceita/rejeita corretamente;
  recuperação de senha gera o e-mail no Mailpit e o link redefine a senha uma única vez.
- ✅ Concluída em 2026-11-16 (fiapx-auth#4). A entrega do e-mail no Mailpit depende do `fiapx-notification`
  e é conferida na Etapa 6; até lá, o `PASSWORD_RESET` é validado na fila pelo contract test e pela
  integração. Localmente, `npm run dev` imita o API Gateway (o LocalStack Community não emula o HTTP API).

### Etapa 4 — fiapx-video-api

- Ordem: Domain (VOs, `Video`, `ProcessingSaga`, `ProcessingQuota`) com testes unitários → Application
  (use cases com Mockery) → Infrastructure (Eloquent, S3, SQS, outbox) → Presentation (controllers,
  requests, commands) → BDD (Behat) da SAGA → OpenAPI → Dockerfile → `k8s/`.
- **DoD:** cobertura ≥ 80%; os cenários BDD do §6.4 passam; o fluxo local funciona com o processor simulado.

### Etapa 5 — fiapx-video-processor

- Domain → use cases → adapters (ffmpeg, zip, S3, SQS, heartbeat) → comando consumidor → testes
  (unit + integração com ffmpeg real) → Dockerfile → `k8s/` + `ScaledObject`.
- **DoD:** fluxo ponta a ponta **local**: upload no LocalStack → saga → processor → `COMPLETED` → download
  do zip com os frames.

### Etapa 6 — fiapx-notification

- Domínio, use case, handler SQS, templates, SES/Mailpit, repositório DynamoDB (§8.6.2), respostas à
  saga, Terraform (fila + DLQ + Lambda + tabela), testes.
- **DoD:** vídeo inválido no fluxo local gera um e-mail no Mailpit, um item `SENT` no DynamoDB (LocalStack)
  com PK = e-mail do usuário, e a saga termina em `NOTIFIED`. Mensagem duplicada não gera segundo e-mail.
  O e-mail de redefinição pedido ao `fiapx-auth` também chega ao Mailpit (pendência da Etapa 3).

### Etapa 6.5 — fiapx-web

- Implementar em React o layout do Google Stitch (`fiapx-web/stitch_fiap_x_video_processor_front_end/`),
  seguindo o `DESIGN.md` e os contratos do `Prompt-layout-web.md`.
- Integrar aos contratos reais (`/api/auth/*`, `/api/videos*`, POST pré-assinado no S3), testes e build.
- **DoD:** no ambiente local, cadastro → login → upload de 3 vídeos ao mesmo tempo → status atualizando
  sozinho → download dos zips.

### Etapa 7 — Infra AWS (fiapx-infra) 🛑

- Escrever todos os módulos do §8.2, testar no LocalStack e abrir PR com o `plan` comentado.
- O `apply` acontece **pelo GitHub Actions** ao fazer merge (§11.5). O agente **não faz merge** desse PR:
  o time revisa o `plan` e faz o merge (gera custo).
- Pedir ao time o registro manual do domínio `hackfiapf5.click` (§8.6.4). Depois do apply, conferir a
  verificação DKIM no SES e verificar os e-mails dos integrantes como destinatários (sandbox).
- **DoD:** `apply` do CI OK e parâmetros SSM publicados.

### Etapa 8 — CI/CD

- Workflows do §11 em cada repositório; SonarCloud configurado; OIDC funcionando (`sub` com
  `job_workflow_ref`).
- `deploy.yml` reutilizável em cada repositório (`push` na `main` + `workflow_call`) e o orquestrador
  `deploy-all.yml`/`destroy-all.yml` no `fiapx-infra` (ADR-018).
- **DoD:** um PR em cada repositório com todos os checks verdes; merge na `main` faz deploy sozinho;
  `destroy-all` seguido de `deploy-all` derruba e sobe o ambiente inteiro com o smoke ponta a ponta verde.

### Etapa 9 — Observabilidade

- New Relic no cluster, nas imagens e nas Lambdas; eventos customizados; dashboard e alertas importados.
- **DoD:** dashboard com dados reais de um processamento na AWS.

### Etapa 10 — Validação de carga e entregáveis 🛑

- Script **k6** (`fiapx-docs/tests/load/`) enviando, por exemplo, 30 vídeos curtos em 1 minuto. Coletar
  evidências: fila crescendo, KEDA escalando o worker, todos os vídeos `COMPLETED`, nenhuma mensagem perdida.
- Finalizar a documentação com evidências (prints de cobertura, Sonar, dashboard, pipelines, k6).
- Gerar o PDF de entrega e revisar o roteiro do vídeo (≤ 10 min).
- **DoD:** checklist do §14 todo marcado.

---

## 13. Regras para o agente

1. **Documentação antes do código.** Não escrever código de aplicação antes da aprovação da Etapa 1.
2. **Nunca** commitar segredos (`.env`, chaves JWT, credenciais). Usar `.env.example`, Secrets Manager e
   GitHub Secrets.
3. `terraform apply`/`destroy` na AWS **somente pelo GitHub Actions** (merge na `main` revisado pelo time,
   ou `deploy-all.yml`/`destroy-all.yml` manuais). Apply local só no LocalStack ou, quando realmente necessário para teste,
   seguindo §11.5 e com autorização do time.
4. Seguir DDD + Clean Architecture à risca: Domain sem Laravel/Eloquent/AWS SDK; dependências apontam
   para dentro; toda interface é ligada no `RepositoryServiceProvider`.
5. Exceções: VOs lançam `\InvalidArgumentException`, regras de negócio lançam `\DomainException` (→ 422),
   recurso inexistente → 404 via handler global. Sem try/catch em controllers e use cases (exceção
   permitida: o loop dos consumidores, que precisa decidir entre ack e retry).
6. Commits no padrão **Conventional Commits**, uma branch e um PR por etapa e repositório, descrição do PR
   com o que foi feito e como testar.
7. Rodar `./vendor/bin/pint`, `phpstan`, `npm run lint` e os testes antes de cada commit.
8. Toda decisão nova, ou que contrarie este documento, deve virar **ADR** e ser comunicada ao time.
9. Textos de documentação, README e mensagens ao usuário em **português do Brasil** com acentuação
   correta; identificadores de código em inglês.
10. Se algo neste documento estiver ambíguo ou impossível (limite de conta AWS, SES sandbox etc.),
    **perguntar ao time** em vez de assumir.
11. **Todo repositório tem um `README.md` sempre atualizado** (propósito, stack, como rodar, como testar,
    variáveis de ambiente, diagrama e links). Toda mudança que altere algum desses pontos atualiza o README
    **no mesmo PR**; o template de PR tem esse item no checklist.

---

## 14. Entregáveis finais e checklist

### Documentação

- [ ] Domain Storytelling (6 histórias)
- [ ] C4 (contexto, containers, componentes) e diagramas de sequência
- [ ] 18 ADRs e 10 RFCs
- [ ] Imagens PNG/SVG de todos os diagramas (`fiapx-docs/diagramas/`, por assunto)
- [ ] SAGA documentada (passos, estados, compensações)
- [ ] Fluxo de deploy e ambientes
- [ ] Modelo de dados (ER) e **scripts de criação** (SQL + Terraform)
- [ ] OpenAPI e contratos de mensagens
- [ ] Observabilidade (dashboard + alertas)

### Código e infra

- [ ] 7 repositórios em <https://github.com/hackathon-fiap-soat> com README (propósito, stack, como rodar, diagrama, links)
- [ ] Front-end publicado no CloudFront (link no PDF de entrega)
- [ ] Remetente SES verificado (domínio com DKIM) e histórico de envios no DynamoDB
- [ ] `main` protegida + PR obrigatório + checks
- [ ] Cobertura ≥ 80% em cada serviço + BDD da SAGA + SonarCloud aprovado
- [ ] CI/CD com deploy automático (EKS e Lambdas)
- [ ] Acesso do usuário `soat-architecture` em todos os repositórios

### Requisitos do enunciado

- [ ] RF1 vários vídeos em paralelo (evidência k6 + KEDA)
- [ ] RF2 nenhuma requisição perdida em pico (fila + DLQ + outbox)
- [ ] RF3 usuário e senha (API Gateway + Lambda)
- [ ] RF4 listagem de status
- [ ] RF5 notificação de erro por e-mail
- [ ] RT1–RT5 (persistência, escalável, GitHub, testes, CI/CD)

### Apresentação

- [ ] PDF de entrega: participantes (Diego Fenille – rm372271, Eduardo Santos – rm373573), links dos
      repositórios, link do vídeo, link da documentação
- [ ] Vídeo de **até 10 minutos**: documentação → arquitetura → demonstração (login, upload de vários
      vídeos, status mudando, download do zip, vídeo inválido gerando e-mail, KEDA escalando, dashboard,
      pipeline)
