# RFC-009 — Hospedagem do front-end

- **Status:** Aprovada
- **Data:** 2026-11-16
- **Autores:** Diego Fenille, Eduardo Santos
- **ADR resultante:** ADR-014

## Resumo

Propomos que o `fiapx-web` (SPA **React + Vite + TypeScript + Tailwind**) seja publicado como arquivos
estáticos em um **bucket S3 privado** servido por **CloudFront** com OAC. A mesma distribuição encaminha
`/api/*` para o API Gateway, de modo que front-end e API ficam **na mesma origem** e o navegador não faz
chamadas cross-origin para a API.

## Motivação

O enunciado não exige interface gráfica, mas a demonstração em vídeo precisa mostrar cadastro, login,
upload de vários vídeos, status mudando e download do zip. No projeto base, a página HTML era uma string
embutida no `main.go` (`getHTMLForm()`), sem autenticação e com CORS `*`. Queremos:

- hospedagem barata, sem servidor para operar e com HTTPS;
- remover CORS da API (menos superfície de erro e de ataque);
- deploy independente do back-end, pelo pipeline do próprio repositório.

## Proposta

- Bucket do site privado (Block Public Access), lido só pelo CloudFront via **Origin Access Control**.
- Comportamentos do CloudFront: `/*` → bucket do site (com fallback para `index.html` nas rotas da SPA);
  `/api/*` → API Gateway, sem cache e repassando o header `Authorization`, sem reescrita de caminho.
- `VITE_API_BASE_URL=/api`; token JWT em memória + `sessionStorage`; 401 → volta para o login.
- O upload é a **única** chamada cross-origin: vai direto ao bucket de vídeos (RFC-002), com CORS do
  bucket restrito ao domínio do CloudFront.
- Infra criada pelo `fiapx-infra` (módulo `web-hosting`), que publica `/fiapx/prod/web/bucket`,
  `/web/cloudfront_distribution_id` e `/web/url` no SSM.
- Pipeline: `npm run build` → `aws s3 sync dist/` → invalidação do CloudFront → smoke com Playwright na
  URL pública.
- Modo mock (MSW) para desenvolver e demonstrar o layout sem back-end.

## Alternativas

| Critério | S3 + CloudFront (proposta) | AWS Amplify Hosting | Container (nginx) no EKS |
| --- | --- | --- | --- |
| Custo aproximado | Muito baixo (armazenamento + transferência) | Baixo (build + hospedagem) | Consome nós do EKS e precisa de ingress público |
| Complexidade operacional | Baixa | Muito baixa (CI próprio do Amplify) | Média (imagem, deployment, ingress, TLS) |
| Mesma origem para `/api/*` | Sim, com comportamento do CloudFront | Possível com rewrites, menos controle | Possível com ingress, mas expõe o cluster |
| Infra como código no Terraform | Total (módulo `web-hosting`) | Parcial (app e branch; build fora do nosso CI) | Total |
| CI/CD no GitHub Actions com OIDC | Sim | Duplica com o pipeline do Amplify | Sim |
| Escalabilidade e disponibilidade | Alta (edge global) | Alta (usa CloudFront) | Limitada às réplicas e ao ALB |
| Segurança | Bucket privado + OAC + HTTPS do CloudFront | Gerenciada | Superfície maior: cluster exposto à internet |
| Lock-in | Médio (arquivos estáticos são portáveis) | Alto | Baixo |
| Curva de aprendizado do time | Baixa | Baixa | Baixa (K8s conhecido), mas mais trabalho |
| Aderência ao enunciado | Neutra (front-end é apoio à demonstração) | Neutra | Neutra |

## Riscos

- **Cache servindo versão antiga** após deploy. Mitigação: arquivos com hash do Vite e invalidação no
  pipeline; `index.html` com cache curto.
- **Comportamento `/api/*` cacheando respostas autenticadas.** Mitigação: política "caching disabled" e
  repasse explícito de `Authorization` e query strings.
- **Fallback da SPA mascarando erros da API** (403/404 → `index.html`). Mitigação: fallback aplicado só
  ao comportamento do bucket do site.
- **Token em `sessionStorage` exposto a XSS.** Mitigação: React escapa saída, sem `dangerouslySetInnerHTML`
  e expiração de 1 hora.
- **Dependência circular de CORS** (bucket de vídeos precisa do domínio do CloudFront). Mitigação: ambos
  no mesmo `apply` do `fiapx-infra`.

## Decisão

Aprovada: front-end React + Vite em S3 privado + CloudFront com OAC, com `/api/*` na mesma origem e
deploy por `s3 sync` + invalidação no GitHub Actions. A decisão é registrada na **ADR-014**.
