# Roteiro do vídeo (até 10 minutos)

Ordem pedida no enunciado: documentação → arquitetura → projeto funcionando. Os tempos somam 9min30s,
com 30 s de folga.

| Tempo | Bloco | O que mostrar | Quem fala |
|---|---|---|---|
| 0:00–0:40 | Abertura | Equipe, problema da FIAP X e os limites do projeto base (síncrono, disco local, sem usuário) | a definir |
| 0:40–2:00 | Documentação | `fiapx-docs`: Domain Storytelling (DS-02 e DS-04), linguagem ubíqua, ADRs e RFCs (destacar as que divergem da stack sugerida: SQS, MySQL, New Relic) | a definir |
| 2:00–3:40 | Arquitetura | C4 de containers, fluxo de upload direto ao S3, SAGA (estados e compensações), filas e DLQs, segurança (JWT RS256 + authorizer) | a definir |
| 3:40–4:20 | Infra e CI/CD | Organização no GitHub, `main` protegida, uma pipeline verde, SonarCloud, `deploy-all` subindo os serviços na ordem | a definir |
| 4:20–6:40 | Demonstração | Cadastro → login → upload de 3 vídeos ao mesmo tempo → status mudando sozinho → download de um zip e abertura das imagens | a definir |
| 6:40–7:40 | Falha | Upload de um vídeo corrompido → status `FAILED` com motivo legível → e-mail recebido → item `SENT` no DynamoDB | a definir |
| 7:40–8:50 | Escala | Teste k6 com 30 vídeos: fila crescendo (CloudWatch), KEDA subindo pods (`kubectl get pods -w` ou dashboard), todos `COMPLETED`, DLQs vazias | a definir |
| 8:50–9:30 | Observabilidade e fechamento | Dashboard do New Relic (status, p95, réplicas, Lambdas), alarmes do CloudWatch (filas e DLQs), e resumo de como cada requisito foi atendido | a definir |

## Preparação antes de gravar

- [ ] Sessão da AWS Academy Learner Lab iniciada e os 3 Secrets `AWS_*` atualizados no GitHub (a sessão
      dura ~4 h: gravar logo depois do `deploy-all`).
- [ ] Ambiente `prod` no ar pelo `deploy-all.yml` (fiapx-infra), com o smoke test ponta a ponta verde.
- [ ] Usuário de demonstração cadastrado com um e-mail real (o e-mail sai pelo provedor SMTP; conferir a
      caixa de spam).
- [ ] Três vídeos curtos válidos e um arquivo corrompido com extensão `.mp4`.
- [ ] Dashboard do New Relic aberto no intervalo certo.
- [ ] Script k6 testado uma vez antes da gravação.
- [ ] Abas abertas: documentação, front-end, AWS Console (SQS, CloudWatch e DynamoDB), New Relic, GitHub Actions.

## Depois de gravar

- [ ] Conferir a duração (≤ 10 min).
- [ ] Publicar (YouTube não listado ou Google Drive com acesso por link).
- [ ] Colocar o link em [`entrega-fase5.md`](entrega-fase5.md) e gerar o PDF.
- [ ] Rodar o `destroy-all.yml` (fiapx-infra) para desligar o ambiente.
