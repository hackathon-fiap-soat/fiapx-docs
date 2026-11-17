# ADR-020 — E-mail pelo OCI Email Delivery no lugar do Brevo

- **Status:** Aceito
- **Data:** 2026-11-17
- **Decisores:** Diego Fenille, Eduardo Santos
- **Relacionados:** [ADR-013](ADR-013-notificacao-sqs-lambda-ses-e-historico-no-dynamodb.md), [ADR-017](ADR-017-recuperacao-e-troca-de-senha.md), [ADR-019](ADR-019-deploy-na-aws-academy-learner-lab.md)
- **Substitui:** o provedor padrão do [ADR-019 §5](ADR-019-deploy-na-aws-academy-learner-lab.md#5-e-mail-por-smtp-externo-no-lugar-do-ses) (Brevo); o resto do §5 continua valendo

## Contexto

O ADR-019 trocou o SES (negado na AWS Academy) por SMTP autenticado num provedor externo, com o Brevo como
padrão. Nos testes na AWS em 2026-11-17, o Brevo aceitava as mensagens (item `SENT` no DynamoDB), mas elas
não chegavam ao destinatário: o remetente era um e-mail pessoal verificado como *single sender*, sem
domínio próprio autenticado, e os provedores de caixa de entrada descartavam as mensagens.

O adaptador já é genérico (Nodemailer, com host, porta, usuário, senha e remetente como configuração), então
trocar de provedor não muda código de aplicação.

## Decisão

- O e-mail sai pelo **OCI Email Delivery** (Oracle Cloud), região São Paulo:
  `smtp.email.sa-saopaulo-1.oci.oraclecloud.com:587`, STARTTLS obrigatório.
- Usuário e senha são **credenciais SMTP** geradas no OCI para um usuário IAM do time (o usuário tem o formato
  `ocid1.user...@ocid1.tenancy...`). Elas ficam nos GitHub Secrets `SMTP_USER` e `SMTP_PASSWORD`, como antes.
- O remetente (`SMTP_FROM`, com nome de exibição) é um **Approved Sender** do OCI num domínio do time. Ele
  também é um Secret: o endereço não aparece no repositório nem no `plan` (variável `sensitive`).
- O host passa a ser o padrão da variável `smtp_host` do `fiapx-notification`; porta, Secrets Manager, SSM e
  o fluxo do deploy não mudam. Os Secrets também ficam no `fiapx-infra`, porque o `deploy-all` chama o deploy
  da notificação com `secrets: inherit`.
- Validado em 2026-11-17: login SMTP e envio aceitos (`250 Ok`) e mensagem recebida na caixa de entrada.

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Continuar no Brevo | Envio aceito mas não entregue com remetente pessoal; exigiria autenticar um domínio no Brevo |
| Gmail SMTP com senha de app | Atrelado a uma conta pessoal, limites baixos e risco de bloqueio por uso automatizado |
| SES | Negado na AWS Academy (ADR-019) |

## Consequências

### Positivas

- Mensagens entregues de fato, com remetente aprovado num domínio do time.
- Nenhuma mudança no código da Lambda nem nos contratos; só configuração.
- Camada gratuita do OCI suficiente para o volume do projeto.

### Negativas / riscos

- Mais uma conta de nuvem (Oracle) para o time manter.
- Sem SPF/DKIM configurados no domínio, a mensagem pode cair no spam.
- As credenciais SMTP do OCI são de um usuário IAM: se ele for removido ou a credencial revogada, o envio falha.

### Mitigações

- Falha de envio continua virando `FAILED` no DynamoDB e, esgotadas as tentativas, `NotificationFailed` e
  alerta da DLQ (nada muda no tratamento de erros).
- O smoke do `deploy-all` exige o item `SENT` quando o Secret `SMTP_FROM` existe.
- Na demonstração, conferir também a caixa de spam; configurar SPF e DKIM do domínio no OCI quando possível.
