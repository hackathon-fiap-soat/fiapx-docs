# Contrato do JWT

O token de acesso é emitido pelo `fiapx-auth` (Node.js) e validado em dois lugares:

1. pelo **Lambda Authorizer** do `fiapx-auth`, no API Gateway;
2. pelo **`fiapx-video-api` (Laravel)**, de novo, como defesa em profundidade
   ([ADR-004](../../04-adrs/ADR-004-autenticacao-api-gateway-lambda-authorizer-jwt-rs256.md)). Ele também é
   a aplicação que roda autenticada, então precisa aceitar e recusar **exatamente** os mesmos tokens que o
   authorizer.

Para garantir isso, as duas implementações seguem as regras abaixo e rodam os mesmos
[vetores de teste](vetores.json).

## Formato

| Parte | Valor |
|---|---|
| Header | `{"alg": "RS256", "typ": "JWT"}` |
| `sub` | id do usuário (UUID v7) |
| `email` | e-mail do usuário, em minúsculas |
| `name` | nome do usuário |
| `iss` | `fiapx-auth` |
| `aud` | `fiapx-api` |
| `iat`, `exp` | emissão e expiração (epoch em segundos); validade de 3600 s |

Chave: RSA 2048. A privada fica no Secrets Manager (`fiapx/<env>/auth/jwt-private-key`); a pública, em PEM,
no SSM (`/fiapx/<env>/auth/jwt_public_key`). No ambiente local, o init do LocalStack gera um par novo a cada
subida, e os dois serviços leem a mesma chave pública do SSM local.

## Regras de validação (iguais nos dois serviços)

1. Aceitar **somente `RS256`**. Recusar `none`, `HS256` e qualquer outro `alg`, inclusive o ataque de
   *algorithm confusion* (HMAC usando a chave pública como segredo).
2. Verificar a assinatura com a chave pública.
3. `iss` igual a `fiapx-auth` e `aud` igual a `fiapx-api` (ou contendo `fiapx-api`, se vier como lista).
4. `exp` obrigatório e no futuro; `nbf`, se existir, no passado. Tolerância de relógio de **30 s**.
5. `sub`, `email` e `name` obrigatórios.
6. Qualquer falha é tratada como token inválido, sem detalhar o motivo ao cliente. O authorizer responde
   `isAuthorized: false` (o API Gateway devolve 403); o `video-api` responde 401.

Contexto repassado depois da validação: `user_id` (= `sub`), `email` e `name`, que o API Gateway envia ao
`video-api` como `x-user-id`, `x-user-email` e `x-user-name`. O `video-api` usa o que vem do JWT revalidado e
confere se os headers batem.

## Vetores de teste

[`vetores.json`](vetores.json) traz a chave pública de teste ([`public-key.test.pem`](public-key.test.pem)) e
13 tokens com o resultado esperado: um válido (expira em 2100) e doze inválidos (expirado, emissor ou
audiência errados, outra chave, payload adulterado, `HS256`, `none`, sem `exp`, sem `sub`, sem `email`,
`nbf` no futuro e mal formado).

- `fiapx-auth`: `tests/contract/jwt.test.js` roda todos os vetores no verificador do authorizer.
- `fiapx-video-api`: o teste equivalente em PHPUnit roda os mesmos vetores no validador do Laravel
  (Etapa 4). Sugestão de biblioteca: `firebase/php-jwt` com `new Key($chave, 'RS256')` e `JWT::$leeway = 30`,
  conferindo `iss`, `aud` e as claims obrigatórias depois do `decode`.

Para gerar de novo (chave e tokens novos): `node scripts/gerar-vetores-jwt.js`. A chave privada de teste é
descartada; nada secreto fica no repositório.
