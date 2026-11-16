#!/usr/bin/env node
'use strict';

/**
 * Gera contracts/jwt/ (chave pública de teste + vetores) para os testes de validação de JWT do
 * fiapx-auth (Node) e do fiapx-video-api (Laravel). Os dois precisam aceitar e recusar exatamente os
 * mesmos tokens.
 *
 * A chave privada é criada em memória, usada para assinar e descartada: nada secreto é versionado.
 * Rodar de novo gera outra chave e outros tokens (os testes leem tudo daqui, então continuam válidos).
 *
 * Uso: node scripts/gerar-vetores-jwt.js
 */
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const DESTINO = path.join(__dirname, '..', 'contracts', 'jwt');
const b64 = (v) => Buffer.from(typeof v === 'string' ? v : JSON.stringify(v)).toString('base64url');

const par = () => crypto.generateKeyPairSync('rsa', {
  modulusLength: 2048,
  publicKeyEncoding: { type: 'spki', format: 'pem' },
  privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
});
const { publicKey, privateKey } = par();
const outra = par().privateKey;

function rs256(payload, chave = privateKey, header = { alg: 'RS256', typ: 'JWT' }) {
  const corpo = `${b64(header)}.${b64(payload)}`;
  return `${corpo}.${crypto.sign('sha256', Buffer.from(corpo), chave).toString('base64url')}`;
}

const SUB = '0192f1c4-6a00-7b00-8c00-1d2e3f4a5b6c';
const IAT = 1_794_000_000; // 2026-11-07
const FUTURO = 4_102_444_800; // 2100-01-01
const base = {
  sub: SUB, email: 'maria.silva@example.com', name: 'Maria Silva',
  iss: 'fiapx-auth', aud: 'fiapx-api', iat: IAT, exp: FUTURO,
};
const sem = (campo) => Object.fromEntries(Object.entries(base).filter(([k]) => k !== campo));

const valido = rs256(base);
const [h, , s] = valido.split('.');

const vetores = [
  { nome: 'valido', descricao: 'Token emitido pelo login, com todas as claims', token: valido, valido: true,
    contexto: { user_id: SUB, email: base.email, name: base.name } },
  { nome: 'expirado', descricao: 'exp no passado (2020)', token: rs256({ ...base, iat: 1_577_836_800, exp: 1_577_840_400 }), valido: false },
  { nome: 'emissor_errado', descricao: 'iss diferente de fiapx-auth', token: rs256({ ...base, iss: 'outro' }), valido: false },
  { nome: 'audiencia_errada', descricao: 'aud diferente de fiapx-api', token: rs256({ ...base, aud: 'outra-api' }), valido: false },
  { nome: 'outra_chave', descricao: 'Assinado com outra chave privada', token: rs256(base, outra), valido: false },
  { nome: 'adulterado', descricao: 'Payload trocado depois da assinatura', token: `${h}.${b64({ ...base, sub: 'outro-usuario' })}.${s}`, valido: false },
  { nome: 'alg_hs256', descricao: 'Algorithm confusion: HS256 usando a chave pública como segredo',
    token: (() => {
      const corpo = `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64(base)}`;
      return `${corpo}.${crypto.createHmac('sha256', publicKey).update(corpo).digest('base64url')}`;
    })(), valido: false },
  { nome: 'alg_none', descricao: 'alg none, sem assinatura', token: `${b64({ alg: 'none', typ: 'JWT' })}.${b64(base)}.`, valido: false },
  { nome: 'sem_exp', descricao: 'Sem a claim exp', token: rs256(sem('exp')), valido: false },
  { nome: 'sem_sub', descricao: 'Sem a claim sub', token: rs256(sem('sub')), valido: false },
  { nome: 'sem_email', descricao: 'Sem a claim email', token: rs256(sem('email')), valido: false },
  { nome: 'nbf_futuro', descricao: 'nbf no futuro (2100)', token: rs256({ ...base, nbf: FUTURO - 1 }), valido: false },
  { nome: 'mal_formado', descricao: 'Não tem três partes', token: 'abc.def', valido: false },
];

fs.mkdirSync(DESTINO, { recursive: true });
fs.writeFileSync(path.join(DESTINO, 'public-key.test.pem'), publicKey);
fs.writeFileSync(path.join(DESTINO, 'vetores.json'), `${JSON.stringify({
  descricao: 'Vetores de teste de validação do JWT do FIAP X. Gerados por scripts/gerar-vetores-jwt.js; a chave privada foi descartada.',
  chave_publica: 'public-key.test.pem',
  regras: { alg: 'RS256', iss: 'fiapx-auth', aud: 'fiapx-api', claims_obrigatorias: ['sub', 'email', 'name', 'exp'], tolerancia_relogio_s: 30 },
  vetores,
}, null, 2)}\n`);
console.log(`${vetores.length} vetores em contracts/jwt/`);
