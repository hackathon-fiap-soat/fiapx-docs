#!/usr/bin/env bash
# Roda o teste de carga contra o prod e coleta as evidências da Etapa 10 enquanto ele roda:
# profundidade da fila processing-commands, réplicas do video-processor (KEDA), pods e mensagens nas DLQs.
#
# Pré-requisitos: credenciais do lab no ambiente (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
# AWS_SESSION_TOKEN), aws CLI, kubectl e Docker (o k6 roda na imagem oficial; não precisa instalar).
# Uso: ./executar.sh            (30 vídeos em 1 minuto)
#      VIDEOS=60 JANELA=2m ./executar.sh
set -euo pipefail

cd "$(dirname "$0")"
export AWS_REGION="${AWS_REGION:-us-east-1}"
K6_IMAGEM="grafana/k6:1.3.0"
ssm() { aws ssm get-parameter --name "/fiapx/prod/$1" --query Parameter.Value --output text; }

api=$(ssm apigw/url)
fila=$(ssm sqs/processing-commands/url)
cluster=$(ssm eks/cluster_name)
saida="evidencias/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$saida"

kube="$saida/.kubeconfig"
aws eks update-kubeconfig --name "$cluster" --kubeconfig "$kube" >/dev/null
k() { kubectl --kubeconfig "$kube" -n fiapx "$@"; }

echo "API: $api"
echo "Evidências em $saida"

# Amostra a cada 15 s (o pollingInterval do KEDA) até o k6 terminar.
coletar() {
  echo "hora,fila_visiveis,fila_em_processamento,replicas_desejadas,pods_prontos,pods_pendentes" >"$saida/amostras.csv"
  while true; do
    read -r vis inv < <(aws sqs get-queue-attributes --queue-url "$fila" \
      --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible \
      --query 'Attributes.[ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible]' --output text)
    desejadas=$(k get deploy video-processor -o jsonpath='{.spec.replicas}')
    prontos=$(k get deploy video-processor -o jsonpath='{.status.readyReplicas}')
    pendentes=$(k get pods -l app.kubernetes.io/name=video-processor --field-selector=status.phase=Pending \
      --no-headers 2>/dev/null | wc -l | tr -d ' ')
    echo "$(date +%H:%M:%S),$vis,$inv,$desejadas,${prontos:-0},$pendentes" | tee -a "$saida/amostras.csv"
    sleep 15
  done
}
coletar &
coletor=$!
trap 'kill $coletor 2>/dev/null || true; rm -f "$kube"' EXIT

docker run --rm -i -v "$PWD:/carga" -w /carga \
  -e API_URL="$api" -e VIDEOS -e JANELA -e COTA -e ESPERA_MIN -e FRAMES_ESPERADOS \
  "$K6_IMAGEM" run --summary-export "$saida/resumo-k6.json" carga.js 2>&1 | tee "$saida/k6-saida.txt"
k6_status=${PIPESTATUS[0]}

kill "$coletor" 2>/dev/null || true
k get scaledobject,hpa >"$saida/keda.txt" 2>&1 || true
k get events --field-selector involvedObject.kind=HorizontalPodAutoscaler \
  --sort-by=.lastTimestamp >>"$saida/keda.txt" 2>&1 || true

# Nenhuma mensagem perdida: todas as DLQs vazias.
echo "dlq,mensagens" >"$saida/dlqs.csv"
for nome in $(aws ssm get-parameters-by-path --path /fiapx/prod/sqs --recursive \
  --query 'Parameters[?ends_with(Name, `-dlq/url`)].Value' --output text); do
  n=$(aws sqs get-queue-attributes --queue-url "$nome" --attribute-names ApproximateNumberOfMessages \
    --query Attributes.ApproximateNumberOfMessages --output text)
  echo "${nome##*/},$n" >>"$saida/dlqs.csv"
done
cat "$saida/dlqs.csv"

pico=$(tail -n +2 "$saida/amostras.csv" | cut -d, -f4 | sort -n | tail -1)
echo "Pico de réplicas do video-processor: ${pico:-?}"
exit "$k6_status"
