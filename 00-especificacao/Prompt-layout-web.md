# Prompt — Layout mínimo do front-end FIAP X (`fiapx-web`)

> Copie o bloco abaixo inteiro e cole na ferramenta de geração de UI que preferirem (Claude, v0, Lovable,
> Bolt etc.). O resultado vai para o repositório `https://github.com/hackathon-fiap-soat/fiapx-web`.
> A especificação completa do sistema está em `Projeto-hackton.md` (§8.7).

---

```text
Crie um front-end MÍNIMO, limpo e funcional para a plataforma "FIAP X — Processador de Vídeos".
O usuário envia vídeos, o sistema extrai 1 frame por segundo e devolve um arquivo .zip com as imagens.
O processamento é assíncrono (fila), então a interface precisa mostrar o status de cada vídeo.

## Stack obrigatória
- React 18 + Vite + TypeScript (strict)
- Tailwind CSS (sem bibliotecas de componentes pesadas; ícones com lucide-react)
- React Router (rotas) e TanStack Query (requisições, cache e polling)
- MSW (Mock Service Worker) com um modo mock ligado por VITE_USE_MOCKS=true, para o layout funcionar sem back-end
- Vitest + Testing Library
- Todo o texto da interface em português do Brasil, com acentuação correta

## Identidade visual
- Visual minimalista e profissional, fundo claro, um card central por página, cantos arredondados, sombras suaves.
- Cor primária: magenta/rosa FIAP (#ED145B). Neutros em cinza. Suporte a tema escuro via prefers-color-scheme.
- Responsivo (funciona em 360 px de largura) e acessível (labels, foco visível, contraste AA, aria-live nos status).
- Logo em texto: "FIAP X" em negrito + subtítulo "Processador de Vídeos".

## Páginas
1. /cadastro — nome, e-mail, senha e confirmação de senha. Política de senha: 8 a 72 caracteres, com letra
   maiúscula, número e símbolo (mostrar os requisitos e um medidor de força). Ao concluir, vai para /login com aviso de sucesso.
2. /login — e-mail e senha. Ao autenticar, guarda o token e vai para /videos. Links para /cadastro e /recuperar-senha.
2a. /recuperar-senha — e-mail. Sempre mostra "Se o e-mail estiver cadastrado, você receberá as instruções"; o link vale
    30 minutos e é de uso único; permite pedir de novo após 2 minutos.
2b. /redefinir-senha?token=... — ao abrir, chama POST /auth/password/reset/verify e mostra o e-mail mascarado e
    "Expira em N min"; nova senha + confirmação com os requisitos; "Salvar nova senha e entrar" chama
    POST /auth/password/reset, guarda o token recebido e vai para /videos. Token inválido: mensagem + link para pedir outro.
2c. /conta/senha (protegida) — senha atual, nova senha e confirmação; chama PUT /auth/password.
3. /videos (protegida) — página principal:
   a) Cabeçalho com nome do usuário e botão "Sair".
   b) Área de upload com arrastar e soltar, aceitando VÁRIOS arquivos ao mesmo tempo.
      Formatos aceitos: .mp4, .avi, .mov, .mkv, .wmv, .flv, .webm. Tamanho máximo: 500 MB por arquivo (validar no cliente).
      Cada arquivo em envio mostra nome, tamanho e barra de progresso individual (0–100%).
   c) Tabela/lista "Meus vídeos": nome do arquivo, data de envio, status (badge colorido), quantidade de
      frames (quando houver), motivo da falha (quando houver) e botão "Baixar ZIP" (só quando concluído).
      Filtro por status e paginação simples.
      Atualização automática a cada 5 segundos ENQUANTO existir algum vídeo em status não final.
   d) Estado vazio amigável ("Você ainda não enviou nenhum vídeo").
4. Qualquer resposta 401 ou 403 → limpa o token e redireciona para /login com a mensagem "Sua sessão expirou"
   (o authorizer do API Gateway devolve 403 para token inválido ou expirado e 401 quando falta o header).

## Status (badge + texto)
- PENDING_UPLOAD → "Aguardando envio" (cinza)
- UPLOADED → "Recebido" (azul)
- QUEUED → "Na fila" (azul)
- PROCESSING → "Processando" (amarelo, com spinner)
- COMPLETED → "Concluído" (verde)
- FAILED → "Falhou" (vermelho; mostrar failure_reason, que já vem em texto legível)
- EXPIRED → "Expirado" (cinza escuro)
Status finais: COMPLETED, FAILED, EXPIRED.

## Contratos da API (base URL = import.meta.env.VITE_API_BASE_URL, padrão "/api")
Os caminhos abaixo são relativos à base URL: "POST /videos" significa "POST /api/videos".
Todas as rotas, exceto cadastro, login e as de recuperação de senha (forgot, verify, reset), enviam o header Authorization: Bearer <token>.
Erros seguem { "message": string, "errors"?: { [campo]: string[] } } — mostrar errors sob cada campo do formulário.

POST /auth/register   body { name, email, password }            → 201 { id, name, email }
POST /auth/login      body { email, password }                  → 200 { access_token, token_type: "Bearer", expires_in }
POST /auth/password/forgot        body { email }                  → 202 (sempre)
POST /auth/password/reset/verify  body { token }                  → 200 { email_masked, expires_at } | 422
POST /auth/password/reset         body { token, password }        → 200 { access_token, token_type, expires_in } | 422
PUT  /auth/password               body { current_password, new_password } (com Bearer) → 204 | 422
                      (os dados do usuário vêm no payload do JWT: sub, name, email — decodificar sem validar)

POST /videos          body { filename, size_bytes, content_type }
                      → 201 { id, status: "PENDING_UPLOAD", upload: { url, fields: { [k]: string }, expires_at } }
GET  /videos?status=&page=1&per_page=10
                      → 200 { data: Video[], meta: { page, per_page, total } }
GET  /videos/{id}     → 200 Video
GET  /videos/{id}/download → 200 { url, expires_at }   (409 se ainda não estiver concluído)

type Video = {
  id: string; original_name: string; size_bytes: number; status: VideoStatus;
  frame_count: number | null; failure_code: string | null; failure_reason: string | null;
  created_at: string; updated_at: string;
}

## Fluxo de upload (importante)
O arquivo NÃO vai para a nossa API. Para cada arquivo:
1. POST /videos com os metadados → recebe upload.url e upload.fields.
2. Monta um FormData com TODOS os campos de upload.fields e, por ÚLTIMO, o campo "file" com o arquivo.
3. Envia com XMLHttpRequest (POST para upload.url) para conseguir mostrar o progresso (xhr.upload.onprogress).
   Não enviar o header Authorization nessa requisição (é direto para o S3).
4. Ao concluir (status 204/201), invalida a lista de vídeos para o novo item aparecer.
5. Os uploads de vários arquivos rodam em paralelo (máximo 3 simultâneos).
Para baixar: GET /videos/{id}/download e abrir a url retornada (window.location.assign).

## Token
- Guardar o access_token em memória e em sessionStorage (nunca em localStorage).
- Cliente HTTP único (fetch wrapper) que injeta o Bearer e trata 401 e 403.

## Modo mock (MSW)
- Implementar handlers para todas as rotas acima, incluindo o POST de upload "do S3" (url fictícia).
- Simular a evolução de status de cada vídeo criado: QUEUED → PROCESSING → COMPLETED em ~15 s,
  e fazer arquivos cujo nome contenha "erro" terminarem em FAILED com failure_reason
  "O arquivo de vídeo está corrompido ou em um formato que não conseguimos ler".
- Usuário de demonstração já cadastrado: demo@fiapx.com / senha12345.

## Estrutura de pastas
src/
  app/ (router, providers, layout autenticado)
  pages/ (RegisterPage, LoginPage, VideosPage)
  features/auth/ (api, hooks, AuthContext, ProtectedRoute)
  features/videos/ (api, hooks, UploadDropzone, UploadProgressList, VideoTable, StatusBadge)
  shared/ (httpClient, ui/ Button Input Card Badge Spinner Toast, formatters de data e bytes)
  mocks/ (handlers.ts, browser.ts)

## Entregue também
- .env.example com VITE_API_BASE_URL=/api e VITE_USE_MOCKS=true
- README em pt-BR: como rodar (npm i, npm run dev), modo mock, build
- Testes de exemplo: StatusBadge, fluxo de login e validação de arquivo inválido
```
