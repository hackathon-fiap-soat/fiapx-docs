# Teste de carga (k6)

Validação de carga da Etapa 10 ([escalabilidade e resiliência](../../03-arquitetura/escalabilidade-e-resiliencia.md#validação-de-carga)):
envia 30 vídeos curtos em 1 minuto ao `prod` e espera todos terminarem.

## O que é verificado

| Requisito | Evidência |
|---|---|
| RF1: vários vídeos ao mesmo tempo | réplicas do `video-processor` subindo pelo KEDA (`amostras.csv`, `keda.txt`) |
| RF2: nada se perde no pico | os 30 vídeos em `COMPLETED` com 3 frames e todas as DLQs vazias (`dlqs.csv`) |
| Fila absorvendo o pico | `processing-commands` crescendo e esvaziando (`amostras.csv`) |

O teste falha (código de saída diferente de zero) se algum envio der erro, se algum vídeo terminar em
`FAILED` ou se nem todos chegarem a `COMPLETED` no prazo.

## Como funciona

- [`carga.js`](carga.js): no `setup`, cria `ceil(30 / 5)` usuários descartáveis (`carga+<rodada>-<n>@example.com`),
  porque a cota é de 5 vídeos em processamento por usuário. O cenário `envio` faz o fluxo do site: `POST
  /api/videos` e o POST pré-assinado do S3 com o [`video-3s.mp4`](video-3s.mp4) (3 frames a 1 fps). O cenário
  `acompanhamento` consulta `GET /api/videos` de cada usuário a cada 10 s até todos ficarem em status final.
- [`executar.sh`](executar.sh): lê a URL da API, a fila e o cluster do SSM, roda o k6 pela imagem oficial
  (`grafana/k6:1.3.0`, sem instalar nada) e, a cada 15 s, registra a fila, as réplicas e os pods pendentes.
  No fim, guarda o `ScaledObject`, o HPA, os eventos de escala e a contagem das DLQs.

## Como rodar

Com o ambiente no ar (`deploy-all`) e as credenciais do lab exportadas no terminal:

```bash
cd tests/load
./executar.sh                       # 30 vídeos em 1 minuto
VIDEOS=60 JANELA=2m ./executar.sh   # outra carga
```

Requer Docker, `aws` CLI e `kubectl`. As evidências ficam em `evidencias/<data-hora>/`: `k6-saida.txt`,
`resumo-k6.json`, `amostras.csv`, `keda.txt` e `dlqs.csv`. Para os prints da entrega, use também o gráfico
da fila no CloudWatch (`ApproximateNumberOfMessagesVisible` da `processing-commands`).

| Variável | Padrão | Uso |
|---|---|---|
| `VIDEOS` | `30` | total de vídeos |
| `JANELA` | `1m` | tempo em que os envios são espalhados |
| `COTA` | `5` | vídeos em processamento por usuário (define quantos usuários criar) |
| `ESPERA_MIN` | `15` | prazo para todos terminarem |
| `FRAMES_ESPERADOS` | `3` | frames por vídeo |

Os usuários de carga ficam no banco até o próximo `destroy-all`.
