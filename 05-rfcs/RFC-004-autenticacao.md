# RFC-004 — Autenticação

- **Status:** Aprovada
- **Data:** 2026-11-16
- **Autores:** Diego Fenille, Eduardo Santos
- **ADR resultante:** ADR-004

## Resumo

Propomos um serviço de identidade próprio, o `fiapx-auth`: **Lambdas Node.js 24** de `register` e
`login` atrás do API Gateway (HTTP API), usuários no database `fiapx_auth` do Aurora MySQL, senha com
**bcrypt** (custo 12) e emissão de **JWT RS256**. Uma **Lambda Authorizer** valida o token em todas as
rotas protegidas e repassa `x-user-id`, `x-user-email` e `x-user-name` ao `fiapx-video-api`.

## Motivação

O RF3 exige que o sistema seja protegido por usuário e senha. O projeto base não tinha autenticação e
expunha CORS `*`. Queremos:

- validar o acesso **na borda**, antes de a requisição chegar ao EKS;
- um contexto de Identidade separado (bounded context próprio), sem acoplar o `video-api` ao cadastro;
- tokens verificáveis por qualquer serviço sem chamar o emissor (chave pública);
- o e-mail e o nome do usuário disponíveis para a notificação de falha (RF5).

## Proposta

- `POST /api/auth/register` `{name, email, password}` → 201. E-mail único, senha ≥ 8 caracteres,
  bcrypt custo 12, erros genéricos (não revelar se o e-mail existe).
- `POST /api/auth/login` `{email, password}` → `{access_token, token_type: "Bearer", expires_in: 3600}`.
  Claims: `sub`, `email`, `name`, `iss: fiapx-auth`, `aud: fiapx-api`, `exp`.
- **Chaves:** privada no Secrets Manager (só a Lambda `login` lê); pública no SSM, lida pelo authorizer
  e pelo `GatewayUserResolver` do `video-api` (defesa em profundidade).
- **Authorizer:** tipo REQUEST, payload 2.0, respostas simples, **cache de 300 s**; valida assinatura,
  `iss`, `aud` e `exp`.
- **Código:** `src/domain` (`User`, `Email`, `Password`), `src/application` (`RegisterUser`,
  `AuthenticateUser`, `VerifyToken`), `src/infrastructure` (`MysqlUserRepository`, `BcryptHasher`,
  `JwtRs256Signer`) e `src/handlers`. Lambdas dentro da VPC para acessar o Aurora.
- **Proteções:** rate limit no stage do API Gateway; tokens stateless (sem sessão no servidor).

## Alternativas

| Critério | Lambda própria + Aurora (proposta) | Amazon Cognito | JWT emitido pelo próprio Laravel |
| --- | --- | --- | --- |
| Validação na borda | Sim (Lambda Authorizer) | Sim (JWT authorizer nativo) | Não: a requisição chega ao EKS para ser validada |
| Separação de bounded context | Sim: `fiapx-auth` com database próprio | Sim, mas o domínio fica no Cognito | Não: identidade dentro da Gestão de Vídeos |
| Controle do modelo de usuário e das mensagens de erro | Total | Limitado (atributos e fluxos do Cognito) | Total |
| Testabilidade local | Alta (Jest + MySQL do compose) | Baixa (Cognito no LocalStack é recurso pago) | Alta |
| Custo aproximado | Baixo (Lambda por invocação; Aurora já existe) | Baixo no volume do hackathon (camada gratuita) | Incluso nos pods |
| Complexidade operacional | Média (gestão de chaves RS256) | Baixa (gerenciado) | Baixa |
| Recursos prontos (MFA, recuperação de senha) | Não (fora do escopo) | Sim | Não |
| Lock-in | Baixo (JWT padrão) | Alto | Baixo |
| Curva de aprendizado do time | Baixa: Fase 3 já usou API Gateway + Lambda de auth | Média | Baixa |
| Aderência ao enunciado (RF3 "usuário e senha") e à avaliação de arquitetura | Alta: mostra a decisão de segurança explicitamente | Alta, porém com menos código próprio para demonstrar | Média |

## Riscos

- **Vazamento da chave privada.** Mitigação: Secrets Manager com acesso só da role da Lambda `login`;
  nunca em repositório (`.env.example` apenas).
- **Token revogado continua válido até expirar** (stateless + cache de 300 s). Aceito: expiração de
  1 hora e escopo do hackathon sem logout forçado.
- **Cold start das Lambdas dentro da VPC.** Mitigação: pacote enxuto, conexão MySQL reaproveitada entre
  invocações; impacto apenas no login e no primeiro authorizer.
- **Força bruta no login.** Mitigação: rate limit no stage e bcrypt custo 12.
- **Sem recuperação de senha nem MFA.** Fora do escopo do enunciado; o Cognito fica como evolução.

## Decisão

Aprovada: autenticação com API Gateway + Lambdas Node.js 24 (`register`, `login`, `authorizer`),
usuários no `fiapx_auth`, bcrypt e JWT RS256. A decisão é registrada na **ADR-004**.
