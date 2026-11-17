# ADR-021 — Dashboards, alertas e Synthetics do New Relic como código

- **Status:** Aceito
- **Data:** 2026-11-17
- **Decisores:** Diego Fenille, Eduardo Santos
- **Relacionados:** [ADR-011](ADR-011-observabilidade-com-new-relic.md), [ADR-018](ADR-018-orquestracao-do-deploy-no-github-actions.md), [ADR-019](ADR-019-deploy-na-aws-academy-learner-lab.md)

## Contexto

A instrumentação (agente PHP, extensão das Lambdas e `nri-bundle`) já envia dados ao New Relic, mas o
dashboard era um JSON importado à mão e os alertas eram uma tabela na documentação: nada garantia que o que
estava na conta era o que estava no repositório, e um alerta esquecido só seria notado quando faltasse.

Além disso, o ambiente `prod` é recriado a cada sessão da AWS Academy (ADR-019): o endereço do API Gateway
muda a cada `deploy-all`, e qualquer coisa que aponte para ele (um monitor de disponibilidade) fica errada
depois de um `destroy-all`.

## Decisão

- Dashboards, política e condições de alerta, destino de e-mail e o monitor Synthetics são recursos do
  **provider Terraform `newrelic/newrelic`**, numa stack própria: `fiapx-infra/observability/newrelic`, com
  state separado no mesmo bucket (`fiapx-infra/newrelic.tfstate`).
- Os dashboards ficam em JSON no formato de export do New Relic (`dashboards/*.json.tftpl`), com o id da conta
  como variável de template, aplicados por `newrelic_one_dashboard_json`. Mudar um widget é mudar o JSON e
  abrir PR.
- O ciclo de vida acompanha o ambiente: o `deploy-all` aplica a stack depois do smoke (etapa 6 ·
  Observabilidade) e o `destroy-all` a destrói antes de derrubar os serviços. O monitor Synthetics lê o
  endereço da API do SSM (`/fiapx/prod/apigw/url`) e só existe enquanto o ambiente existe; o histórico dos
  dados continua no New Relic.
- Em PR, o workflow `newrelic.yml` roda `fmt`, `validate` e comenta o `plan`; o `apply` acontece no merge e no
  `deploy-all` (ADR-016 e ADR-018). Mudanças que só alteram painéis e alertas não geram custo na AWS, mas
  seguem a mesma regra de merge do `fiapx-infra`.
- Credenciais: a **User key** do New Relic (`NEW_RELIC_API_KEY`, só no `fiapx-infra`) e o id da conta
  (`NEW_RELIC_ACCOUNT_ID`) ficam em GitHub Secrets; os e-mails do time (`ALERT_EMAILS`, os mesmos do SNS) são
  variável `sensitive`.
- Processos PHP de vida curta (o CronJob `schedule:run` do `video-api`) enviam pelo **daemon compartilhado**
  `newrelic-php-daemon` no cluster, e não pelo daemon local do pod, que morria antes do envio.

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Importar JSON e criar alertas pela interface | Sem revisão nem histórico; diverge do repositório; precisa ser refeito a cada conta |
| Criar tudo por script NerdGraph no workflow | Reimplementa o que o provider já faz (estado, diff, destroy) |
| Colocar os recursos no state do `envs/prod` | Um erro de painel bloquearia o apply da infraestrutura; o provider exigiria a User key em todo plan da AWS |
| Monitor Synthetics permanente | O endereço da API muda a cada sessão do lab; com o ambiente desligado, alertaria o tempo todo |

## Consequências

### Positivas

- Painéis e alertas revisados em PR e iguais em qualquer conta (basta trocar os Secrets).
- Alertas e monitor só existem com o ambiente no ar: sem alarme falso fora das sessões do lab.
- O `SagaTimeoutCheck` passa a chegar ao New Relic, viabilizando o alerta de sagas vencidas.

### Negativas / riscos

- Mais um state e mais um job no `deploy-all`/`destroy-all`.
- Dashboards apagados e recriados a cada sessão: links salvos para o dashboard mudam.
- O daemon compartilhado é um pod a mais no cluster (reserva pequena de CPU).

### Mitigações

- A stack é pequena e independente; se falhar, o ambiente já está no ar (a etapa roda depois do smoke).
- O dashboard é encontrado pelo nome ("FIAP X — …") na lista de dashboards.
- O daemon usa requests de 25m de CPU, dentro da folga medida no teste de carga.
