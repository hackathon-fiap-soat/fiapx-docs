# C4 — Nível 1: contexto

A plataforma FIAP X recebe vídeos dos usuários, extrai um frame por segundo e devolve um pacote zip.
Este nível mostra quem usa o sistema e de quais sistemas externos ele depende.

```mermaid
C4Context
  title Contexto do sistema FIAP X

  Person(usuario, "Usuário", "Envia vídeos, acompanha o status e baixa o zip com os frames")
  Person(time, "Time de desenvolvimento", "Mantém o código, a infraestrutura e acompanha os alertas")

  System(fiapx, "Plataforma FIAP X", "Cadastro e login, upload de vídeos, processamento assíncrono, status, download e avisos por e-mail")

  System_Ext(email, "Caixa de e-mail do usuário", "Recebe o aviso de falha e, opcionalmente, o de conclusão")
  System_Ext(smtp, "Provedor SMTP (OCI Email Delivery)", "Envio de e-mails transacionais por SMTP autenticado")
  System_Ext(newrelic, "New Relic", "APM, logs, dashboards e alertas")
  System_Ext(github, "GitHub", "Código, pull requests e GitHub Actions (CI/CD)")
  System_Ext(sonar, "SonarCloud", "Análise estática e Quality Gate")

  Rel(usuario, fiapx, "Usa pelo navegador", "HTTPS")
  Rel(fiapx, smtp, "Pede envio de e-mail", "SMTP com STARTTLS")
  Rel(smtp, email, "Entrega o e-mail", "SMTP")
  Rel(fiapx, newrelic, "Envia métricas, traces e logs", "HTTPS")
  Rel(time, github, "Abre PRs e faz merge")
  Rel(github, fiapx, "Faz deploy", "credenciais do lab em GitHub Secrets")
  Rel(github, sonar, "Envia análise do PR")
  Rel(time, newrelic, "Acompanha dashboards e recebe alertas")
```

## Elementos

| Elemento | Tipo | Responsabilidade |
|---|---|---|
| Usuário | Pessoa | Cadastra-se, faz login, envia vários vídeos, acompanha o status e baixa os zips |
| Time de desenvolvimento | Pessoa | Evolui o sistema por pull requests e responde aos alertas |
| Plataforma FIAP X | Sistema | Todo o escopo do hackathon, rodando na AWS Academy Learner Lab (detalhado no [nível 2](c4-containers.md)) |
| Provedor SMTP (OCI Email Delivery) | Externo | Envio de e-mails a partir de um remetente do time aprovado no provedor ([ADR-019](../04-adrs/ADR-019-deploy-na-aws-academy-learner-lab.md) e [ADR-020](../04-adrs/ADR-020-email-pelo-oci-email-delivery.md)) |
| New Relic | Externo | Observabilidade da aplicação, do cluster e das Lambdas |
| GitHub e SonarCloud | Externos | Versionamento, pipelines de CI/CD e Quality Gate |

## Requisitos atendidos neste nível

- **RF3:** o usuário só usa a plataforma depois de se autenticar.
- **RF5:** a plataforma avisa o usuário por e-mail, via SMTP num provedor externo.
- **RT3 e RT5:** código no GitHub, com CI/CD em GitHub Actions.
