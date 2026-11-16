# Imagens dos diagramas

Imagens geradas a partir dos blocos Mermaid da documentação, organizadas por assunto e na ordem de
leitura, para usar no documento de entrega, em slides e no vídeo. **Não edite estes arquivos à mão**:
altere o diagrama no Markdown de origem e rode `python3 scripts/render-diagrams.py`.

Total: 32 diagramas, cada um em PNG (escala 2x, fundo branco) e SVG.

## Contexto

| Diagrama | Imagens | Origem |
|---|---|---|
| C4 nível 1: contexto do sistema | [PNG](01-contexto/c4-contexto.png) · [SVG](01-contexto/c4-contexto.svg) | [`03-arquitetura/c4-contexto.md`](../03-arquitetura/c4-contexto.md) |
| Mapa de contextos (bounded contexts) | [PNG](01-contexto/mapa-de-contextos.png) · [SVG](01-contexto/mapa-de-contextos.svg) | [`01-contexto/linguagem-ubiqua.md`](../01-contexto/linguagem-ubiqua.md) |

## Domínio (Domain Storytelling)

| Diagrama | Imagens | Origem |
|---|---|---|
| DS-01 Cadastro e login | [PNG](02-dominio/ds-01-cadastro-e-login.png) · [SVG](02-dominio/ds-01-cadastro-e-login.svg) | [`02-domain-storytelling/ds-01-cadastro-e-login.md`](../02-domain-storytelling/ds-01-cadastro-e-login.md) |
| DS-02 Envio de vídeo | [PNG](02-dominio/ds-02-envio-de-video.png) · [SVG](02-dominio/ds-02-envio-de-video.svg) | [`02-domain-storytelling/ds-02-envio-de-video.md`](../02-domain-storytelling/ds-02-envio-de-video.md) |
| DS-03 Processamento com sucesso | [PNG](02-dominio/ds-03-processamento-com-sucesso.png) · [SVG](02-dominio/ds-03-processamento-com-sucesso.svg) | [`02-domain-storytelling/ds-03-processamento-com-sucesso.md`](../02-domain-storytelling/ds-03-processamento-com-sucesso.md) |
| DS-04 Falha e notificação | [PNG](02-dominio/ds-04-falha-e-notificacao.png) · [SVG](02-dominio/ds-04-falha-e-notificacao.svg) | [`02-domain-storytelling/ds-04-falha-e-notificacao.md`](../02-domain-storytelling/ds-04-falha-e-notificacao.md) |
| DS-05 Consulta de status e download | [PNG](02-dominio/ds-05-consulta-status-e-download.png) · [SVG](02-dominio/ds-05-consulta-status-e-download.svg) | [`02-domain-storytelling/ds-05-consulta-status-e-download.md`](../02-domain-storytelling/ds-05-consulta-status-e-download.md) |
| DS-06 Recuperação e troca de senha | [PNG](02-dominio/ds-06-recuperacao-e-troca-de-senha.png) · [SVG](02-dominio/ds-06-recuperacao-e-troca-de-senha.svg) | [`02-domain-storytelling/ds-06-recuperacao-e-troca-de-senha.md`](../02-domain-storytelling/ds-06-recuperacao-e-troca-de-senha.md) |

## Arquitetura

| Diagrama | Imagens | Origem |
|---|---|---|
| C4 nível 3: componentes do fiapx-video-api | [PNG](03-arquitetura/c4-componentes-video-api.png) · [SVG](03-arquitetura/c4-componentes-video-api.svg) | [`03-arquitetura/c4-componentes-video-api.md`](../03-arquitetura/c4-componentes-video-api.md) |
| C4 nível 2: processamento assíncrono (SAGA, worker e notificação) | [PNG](03-arquitetura/c4-containers-assincrono.png) · [SVG](03-arquitetura/c4-containers-assincrono.svg) | [`03-arquitetura/c4-containers.md`](../03-arquitetura/c4-containers.md) |
| C4 nível 2: caminho síncrono (navegador, autenticação e API) | [PNG](03-arquitetura/c4-containers-sincrono.png) · [SVG](03-arquitetura/c4-containers-sincrono.svg) | [`03-arquitetura/c4-containers.md`](../03-arquitetura/c4-containers.md) |
| Camadas DDD + Clean Architecture (ADR-003) | [PNG](03-arquitetura/camadas-clean-architecture.png) · [SVG](03-arquitetura/camadas-clean-architecture.svg) | [`04-adrs/ADR-003-ddd-e-clean-architecture-nos-servicos-laravel.md`](../04-adrs/ADR-003-ddd-e-clean-architecture-nos-servicos-laravel.md) |
| Exposição da API: API Gateway, VPC Link e ALB interno (ADR-010) | [PNG](03-arquitetura/exposicao-da-api.png) · [SVG](03-arquitetura/exposicao-da-api.svg) | [`04-adrs/ADR-010-api-gateway-vpc-link-alb-interno-e-targetgroupbinding.md`](../04-adrs/ADR-010-api-gateway-vpc-link-alb-interno-e-targetgroupbinding.md) |
| Integração entre repositórios via SSM Parameter Store (ADR-001) | [PNG](03-arquitetura/integracao-via-ssm.png) · [SVG](03-arquitetura/integracao-via-ssm.svg) | [`04-adrs/ADR-001-polyrepo-e-integracao-via-ssm-parameter-store.md`](../04-adrs/ADR-001-polyrepo-e-integracao-via-ssm-parameter-store.md) |

## Fluxos (sequências)

| Diagrama | Imagens | Origem |
|---|---|---|
| Fluxo de notificação: SQS, Lambda, DynamoDB e SES (ADR-013) | [PNG](04-fluxos/fluxo-de-notificacao.png) · [SVG](04-fluxos/fluxo-de-notificacao.svg) | [`04-adrs/ADR-013-notificacao-sqs-lambda-ses-e-historico-no-dynamodb.md`](../04-adrs/ADR-013-notificacao-sqs-lambda-ses-e-historico-no-dynamodb.md) |
| Sequência 1: cadastro e login | [PNG](04-fluxos/seq-01-cadastro-e-login.png) · [SVG](04-fluxos/seq-01-cadastro-e-login.svg) | [`03-arquitetura/sequencias.md`](../03-arquitetura/sequencias.md) |
| Sequência 2: upload e processamento com sucesso | [PNG](04-fluxos/seq-02-upload-e-processamento.png) · [SVG](04-fluxos/seq-02-upload-e-processamento.svg) | [`03-arquitetura/sequencias.md`](../03-arquitetura/sequencias.md) |
| Sequência 3: falha no processamento com compensação | [PNG](04-fluxos/seq-03-falha-e-compensacao.png) · [SVG](04-fluxos/seq-03-falha-e-compensacao.svg) | [`03-arquitetura/sequencias.md`](../03-arquitetura/sequencias.md) |
| Sequência 3b: timeout do processamento | [PNG](04-fluxos/seq-03b-timeout.png) · [SVG](04-fluxos/seq-03b-timeout.svg) | [`03-arquitetura/sequencias.md`](../03-arquitetura/sequencias.md) |
| Sequência 4: consulta e download | [PNG](04-fluxos/seq-04-consulta-e-download.png) · [SVG](04-fluxos/seq-04-consulta-e-download.svg) | [`03-arquitetura/sequencias.md`](../03-arquitetura/sequencias.md) |
| Sequência 5: recuperação e troca de senha | [PNG](04-fluxos/seq-05-recuperacao-e-troca-de-senha.png) · [SVG](04-fluxos/seq-05-recuperacao-e-troca-de-senha.svg) | [`03-arquitetura/sequencias.md`](../03-arquitetura/sequencias.md) |

## SAGA

| Diagrama | Imagens | Origem |
|---|---|---|
| Estados da saga | [PNG](05-saga/estados-da-saga.png) · [SVG](05-saga/estados-da-saga.svg) | [`03-arquitetura/saga.md`](../03-arquitetura/saga.md) |

## Dados

| Diagrama | Imagens | Origem |
|---|---|---|
| Cluster Aurora com um database por serviço (ADR-005) | [PNG](06-dados/cluster-aurora.png) · [SVG](06-dados/cluster-aurora.svg) | [`04-adrs/ADR-005-aurora-mysql-serverless-v2-um-database-por-servico.md`](../04-adrs/ADR-005-aurora-mysql-serverless-v2-um-database-por-servico.md) |
| Modelo ER: fiapx_auth e fiapx_video | [PNG](06-dados/modelo-er.png) · [SVG](06-dados/modelo-er.svg) | [`03-arquitetura/modelo-de-dados.md`](../03-arquitetura/modelo-de-dados.md) |

## Segurança, escala e e-mail

| Diagrama | Imagens | Origem |
|---|---|---|
| Escala do worker pelo KEDA | [PNG](07-seguranca-e-escala/escala-keda.png) · [SVG](07-seguranca-e-escala/escala-keda.svg) | [`03-arquitetura/escalabilidade-e-resiliencia.md`](../03-arquitetura/escalabilidade-e-resiliencia.md) |
| Rede e segurança | [PNG](07-seguranca-e-escala/rede-e-seguranca.png) · [SVG](07-seguranca-e-escala/rede-e-seguranca.svg) | [`03-arquitetura/seguranca.md`](../03-arquitetura/seguranca.md) |
| Remetente de e-mail: domínio, DKIM e SES (ADR-015) | [PNG](07-seguranca-e-escala/remetente-de-email-ses.png) · [SVG](07-seguranca-e-escala/remetente-de-email-ses.svg) | [`04-adrs/ADR-015-remetente-de-email-dominio-proprio-e-sandbox-do-ses.md`](../04-adrs/ADR-015-remetente-de-email-dominio-proprio-e-sandbox-do-ses.md) |

## Deploy

| Diagrama | Imagens | Origem |
|---|---|---|
| Ordem de deploy entre repositórios (primeira subida) | [PNG](08-deploy/ordem-de-deploy.png) · [SVG](08-deploy/ordem-de-deploy.svg) | [`06-deploy/fluxo-de-deploy.md`](../06-deploy/fluxo-de-deploy.md) |
| Orquestração do deploy: deploy-all no fiapx-infra (ADR-018) | [PNG](08-deploy/orquestracao-deploy-all.png) · [SVG](08-deploy/orquestracao-deploy-all.svg) | [`04-adrs/ADR-018-orquestracao-do-deploy-no-github-actions.md`](../04-adrs/ADR-018-orquestracao-do-deploy-no-github-actions.md) |
| Pipelines por tipo de repositório | [PNG](08-deploy/pipelines.png) · [SVG](08-deploy/pipelines.svg) | [`06-deploy/fluxo-de-deploy.md`](../06-deploy/fluxo-de-deploy.md) |
| Política de terraform apply (ADR-016) | [PNG](08-deploy/politica-terraform-apply.png) · [SVG](08-deploy/politica-terraform-apply.svg) | [`04-adrs/ADR-016-terraform-apply-somente-via-github-actions.md`](../04-adrs/ADR-016-terraform-apply-somente-via-github-actions.md) |

## Observabilidade

| Diagrama | Imagens | Origem |
|---|---|---|
| Fluxo de telemetria para o New Relic | [PNG](09-observabilidade/fluxo-de-telemetria.png) · [SVG](09-observabilidade/fluxo-de-telemetria.svg) | [`07-observabilidade/observabilidade.md`](../07-observabilidade/observabilidade.md) |
