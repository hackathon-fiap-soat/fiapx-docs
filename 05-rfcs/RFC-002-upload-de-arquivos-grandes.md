# RFC-002 — Upload de arquivos grandes

- **Status:** Aprovada
- **Data:** 2026-11-16
- **Autores:** Diego Fenille, Eduardo Santos
- **ADR resultante:** ADR-006

## Resumo

Propomos que o navegador envie o vídeo **direto ao bucket S3** com um **POST pré-assinado** gerado pelo
`fiapx-video-api` (`POST /api/videos`). A política assinada fixa a chave, o `Content-Type` e o tamanho
máximo (`content-length-range`, até **500 MB**). O vídeo nunca passa pelo API Gateway nem pelos pods, e
a SAGA começa pelo evento `s3:ObjectCreated` → SQS `video-uploaded`, não por uma chamada do cliente.

## Motivação

No projeto base, o vídeo era enviado em `multipart/form-data` para o próprio servidor Go, gravado em
disco local e processado dentro da requisição. Na nova arquitetura, as rotas públicas passam pelo
CloudFront → API Gateway (HTTP API) → VPC Link → ALB interno, e o **API Gateway limita o payload a
10 MB e a integração a 30 s**. Um vídeo comum passa facilmente desses limites.

Também queremos que um pico de uploads não consuma CPU, memória e banda dos pods do `video-api`
(RF2) e que, se o cliente fechar o navegador logo depois do envio, o processamento continue.

## Proposta

1. O cliente chama `POST /api/videos` com `{filename, size_bytes, content_type}`. O `video-api` valida
   extensão e MIME (mp4, avi, mov, mkv, wmv, flv, webm) e o tamanho declarado, cria o `Video` em
   `PENDING_UPLOAD` e devolve `{id, status, upload: {url, fields, expires_at}}`.
2. `S3ObjectStorage` gera o POST pré-assinado com as condições da política:
   - `key` exata, definida pelo servidor sob o prefixo `uploads/` (o cliente não escolhe a chave);
   - `Content-Type` igual ao declarado;
   - `content-length-range` de 1 byte a 500 MB;
   - expiração curta e assinatura SigV4 com a role do pod (EKS Pod Identity).
3. O `fiapx-web` envia `multipart/form-data` ao bucket com os `fields` recebidos e o arquivo como
   **último** campo, usando `XMLHttpRequest` para exibir o progresso.
4. O bucket publica `s3:ObjectCreated` (prefixo `uploads/`) na fila `fiapx-<env>-video-uploaded`. O
   `saga-consumer` inicia a SAGA e o passo `ValidateUpload` confere o objeto com `HeadObject` (defesa
   em profundidade).
5. Se o upload não acontecer em 1 hora, `ExpirePendingUploadsCommand` marca o vídeo como `EXPIRED`.
6. CORS do bucket liberado só para `POST`, com origem igual ao domínio do CloudFront. Lifecycle:
   `uploads/` expira em 7 dias.

## Alternativas

| Critério | Via API (multipart no Laravel) | S3 pré-assinado PUT | S3 pré-assinado POST (proposta) | S3 multipart upload |
| --- | --- | --- | --- | --- |
| Limite de tamanho | 10 MB e 30 s do API Gateway | 5 GB por PUT | 5 GB por POST; nós limitamos a 500 MB | Até 5 TB |
| Controle do tamanho máximo na assinatura | Validação na aplicação | Não há faixa; só um `Content-Length` exato assinado | Sim: `content-length-range` na política | Não por parte; exige controle na aplicação |
| Controle de chave e `Content-Type` | Total | Sim (assinados na URL) | Sim (condições da política) | Sim, mas por parte |
| Carga nos pods e no gateway | Alta (arquivo atravessa tudo) | Nenhuma | Nenhuma | Nenhuma |
| Complexidade no front-end | Baixa | Baixa | Baixa (form + `XMLHttpRequest`) | Alta (dividir, assinar N partes, `CompleteMultipartUpload`) |
| Complexidade no back-end | Média (stream para S3) | Baixa | Baixa | Alta (create/complete/abort, limpeza de uploads incompletos) |
| Retomada após queda de rede | Não | Não | Não | Sim, por parte |
| Escalabilidade em pico | Limitada pelos pods | Escala com o S3 | Escala com o S3 | Escala com o S3 |
| Aderência ao enunciado (RF2) | Fraca: pico derruba a API | Boa | Boa | Boa |

## Riscos

- **Upload interrompido** em conexões ruins: sem retomada. Aceitável para vídeos de até 500 MB; o
  multipart upload fica como evolução se o limite subir.
- **Cliente envia algo diferente do declarado.** Mitigação: a política força chave, tipo e tamanho, e o
  `ValidateUpload` (`HeadObject`) falha com `INVALID_UPLOAD` e compensa com `DeleteUploadedObject`.
- **Evento do S3 entregue em duplicidade** (entrega "at least once"). Mitigação: `uq_sagas_video` e
  `processed_messages` tornam o início da SAGA idempotente.
- **Vazamento da URL assinada.** Mitigação: expiração curta, chave única por vídeo, bucket com Block
  Public Access e SSE-S3.
- **CORS mal configurado** bloqueia o upload. Mitigação: o domínio do CloudFront alimenta o CORS pelo
  Terraform (módulo `web-hosting` → `storage`).

## Decisão

Aprovada: upload direto ao S3 por **POST pré-assinado**, com `content-length-range` limitado a 500 MB e
fields assinados, e início da SAGA pelo evento `s3:ObjectCreated` → SQS. A decisão é registrada na
**ADR-006**.
