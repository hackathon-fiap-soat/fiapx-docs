// Teste de carga da Etapa 10: envia VIDEOS vídeos curtos em JANELA (padrão 30 em 1 minuto) e espera todos
// terminarem. Prova RF1 (vários vídeos em paralelo) e RF2 (nada se perde no pico): todos têm de chegar a
// COMPLETED com o número de frames esperado.
//
// A cota é de 5 vídeos em processamento por usuário, então o setup cria ceil(VIDEOS / COTA) usuários
// descartáveis (@example.com) e distribui os envios entre eles em rodízio.
//
// Uso (veja o README): API_URL=https://<api>.execute-api.us-east-1.amazonaws.com k6 run carga.js
import http from 'k6/http';
import exec from 'k6/execution';
import { check, fail, sleep } from 'k6';
import { Counter, Trend } from 'k6/metrics';
import { FormData } from 'https://jslib.k6.io/formdata/0.0.2/index.js';

const API = (__ENV.API_URL || '').replace(/\/$/, '');
const VIDEOS = Number(__ENV.VIDEOS || 30);
const JANELA = __ENV.JANELA || '1m';
const COTA = Number(__ENV.COTA || 5);
const ESPERA_MIN = Number(__ENV.ESPERA_MIN || 15);
const FRAMES = Number(__ENV.FRAMES_ESPERADOS || 3);
const SENHA = 'Carga-teste-123';

// Lido uma vez no init: vídeo de 3 s (3 frames a 1 fps).
const video = open('./video-3s.mp4', 'b');

const enviados = new Counter('videos_enviados');
const concluidos = new Counter('videos_concluidos');
const falhos = new Counter('videos_falhos');
const pendentes = new Counter('videos_nao_finalizados');
const tempoTotal = new Trend('tempo_ate_completed', true);

const janelaSeg = Number.parseInt(JANELA, 10) * (JANELA.endsWith('m') ? 60 : 1);

export const options = {
  setupTimeout: '2m',
  scenarios: {
    envio: {
      executor: 'shared-iterations',
      exec: 'enviar',
      vus: Math.min(VIDEOS, 10),
      iterations: VIDEOS,
      maxDuration: JANELA,
    },
    acompanhamento: {
      executor: 'per-vu-iterations',
      exec: 'acompanhar',
      vus: 1,
      iterations: 1,
      startTime: `${janelaSeg + 5}s`,
      maxDuration: `${ESPERA_MIN}m`,
    },
  },
  thresholds: {
    'checks{etapa:envio}': ['rate==1'],
    videos_concluidos: [`count==${VIDEOS}`],
    videos_falhos: ['count==0'],
    'http_req_failed{etapa:envio}': ['rate==0'],
  },
};

function json(res) {
  try {
    return res.json();
  } catch {
    return null;
  }
}

export function setup() {
  if (!API) fail('defina API_URL (ex.: https://<api>.execute-api.us-east-1.amazonaws.com)');
  const rodada = Date.now();
  const usuarios = [];
  const total = Math.ceil(VIDEOS / COTA);
  for (let i = 0; i < total; i++) {
    const email = `carga+${rodada}-${i}@example.com`;
    const corpo = JSON.stringify({ name: `Carga ${i}`, email, password: SENHA });
    const params = { headers: { 'content-type': 'application/json' } };
    const reg = http.post(`${API}/api/auth/register`, corpo, params);
    if (reg.status >= 300) fail(`cadastro de ${email} devolveu ${reg.status}: ${reg.body}`);
    const login = http.post(`${API}/api/auth/login`, JSON.stringify({ email, password: SENHA }), params);
    const token = (json(login) || {}).access_token;
    if (!token) fail(`login de ${email} devolveu ${login.status}`);
    usuarios.push({ email, token });
  }
  console.log(`${total} usuários de carga criados; ${VIDEOS} vídeos em ${JANELA}`);
  return { usuarios, inicio: Date.now() };
}

export function enviar(dados) {
  const n = exec.scenario.iterationInTest;
  const { token } = dados.usuarios[n % dados.usuarios.length];
  const tags = { etapa: 'envio' };
  const auth = { authorization: `Bearer ${token}`, 'content-type': 'application/json' };

  const pedido = http.post(
    `${API}/api/videos`,
    JSON.stringify({ filename: `carga-${n}.mp4`, size_bytes: video.byteLength, content_type: 'video/mp4' }),
    { headers: auth, tags: { ...tags, name: 'POST /api/videos' } },
  );
  const criado = json(pedido) || {};
  if (!check(pedido, { 'POST /api/videos 201': (r) => r.status === 201 }, tags)) return;

  // POST pré-assinado do S3: os campos vêm antes do arquivo, e o FormData mantém essa ordem.
  const form = new FormData();
  for (const [k, v] of Object.entries(criado.upload.fields)) form.append(k, v);
  form.append('file', http.file(video, `carga-${n}.mp4`, 'video/mp4'));
  const s3 = http.post(criado.upload.url, form.body(), {
    headers: { 'content-type': `multipart/form-data; boundary=${form.boundary}` },
    tags: { ...tags, name: 'POST S3 (pré-assinado)' },
  });
  if (check(s3, { 'upload no S3 204': (r) => r.status === 204 }, tags)) enviados.add(1);

  // Espalha os envios pela janela (ex.: 30 vídeos / 10 VUs em 60 s → um envio a cada ~20 s por VU).
  sleep((janelaSeg * Math.min(VIDEOS, 10)) / VIDEOS - 1);
}

export function acompanhar(dados) {
  const limite = Date.now() + (ESPERA_MIN * 60 - 30) * 1000;
  const finais = new Set(['COMPLETED', 'FAILED', 'EXPIRED']);
  let videos = [];
  while (Date.now() < limite) {
    videos = [];
    for (const { token } of dados.usuarios) {
      const r = http.get(`${API}/api/videos?per_page=100`, {
        headers: { authorization: `Bearer ${token}` },
        tags: { etapa: 'acompanhamento', name: 'GET /api/videos' },
      });
      videos.push(...((json(r) || {}).data || []));
    }
    const porStatus = {};
    for (const v of videos) porStatus[v.status] = (porStatus[v.status] || 0) + 1;
    console.log(`status: ${JSON.stringify(porStatus)}`);
    if (videos.length >= VIDEOS && videos.every((v) => finais.has(v.status))) break;
    sleep(10);
  }

  for (const v of videos) {
    if (v.status === 'COMPLETED') {
      concluidos.add(1);
      tempoTotal.add(Date.parse(v.updated_at) - Date.parse(v.created_at));
      check(v, { [`${FRAMES} frames por vídeo`]: (x) => x.frame_count === FRAMES }, { etapa: 'resultado' });
    } else if (v.status === 'FAILED') {
      falhos.add(1);
      console.error(`vídeo ${v.id} falhou: ${v.failure_code} ${v.failure_reason}`);
    } else {
      pendentes.add(1);
    }
  }
  const faltando = VIDEOS - videos.length;
  if (faltando > 0) console.error(`${faltando} vídeo(s) não apareceram na listagem`);
}
