# Visão geral

## Problema

A empresa fictícia **FIAP X** tem um protótipo que recebe um vídeo, extrai **um frame por segundo** com
`ffmpeg` e devolve as imagens em um arquivo `.zip`. O protótipo funcionou numa apresentação para
investidores, mas não aguenta uso real: processa um vídeo por vez, dentro da requisição HTTP, sem
usuários, sem banco e sem tratamento de falhas.

O hackathon pede a reconstrução desse sistema como uma solução distribuída, escalável e resiliente,
aplicando arquitetura de software, microsserviços, mensageria, qualidade e CI/CD.

## Objetivos

1. Aceitar vários vídeos ao mesmo tempo, de vários usuários, sem perder nenhuma requisição em picos.
2. Proteger o acesso com usuário e senha.
3. Mostrar ao usuário o status de cada vídeo e permitir o download do zip.
4. Avisar o usuário por e-mail quando um processamento falhar.
5. Entregar tudo versionado, testado, com pipeline de CI/CD e observabilidade.

## Requisitos funcionais

| ID | Requisito | Como atendemos |
|---|---|---|
| RF1 | Processar mais de um vídeo ao mesmo tempo | Workers no EKS escalados pelo tamanho da fila (KEDA, 1 a 10 pods). Cada pod processa 1 vídeo |
| RF2 | Em picos, não perder nenhuma requisição | Upload direto ao S3, evento S3 → SQS (durável), transactional outbox, DLQ e consumidores idempotentes |
| RF3 | Sistema protegido por usuário e senha | API Gateway + Lambdas Node.js (cadastro e login com bcrypt, JWT RS256) + Lambda Authorizer |
| RF4 | Listagem de status dos vídeos do usuário | `GET /api/videos`, paginado e filtrado pelo usuário do token |
| RF5 | Notificar o usuário em caso de erro | A SAGA envia `SendNotification` → Lambda de notificação → e-mail por SMTP num provedor externo (Brevo) |

## Requisitos técnicos

| ID | Requisito | Como atendemos |
|---|---|---|
| RT1 | Persistência dos dados | Aurora MySQL (dados relacionais), DynamoDB (histórico de notificações) e S3 (arquivos) |
| RT2 | Arquitetura escalável | EKS + HPA (API) + KEDA (worker) + serviços gerenciados (SQS, S3, Aurora Serverless v2, Lambda) |
| RT3 | Versionamento no GitHub | Sete repositórios na organização [`hackathon-fiap-soat`](https://github.com/hackathon-fiap-soat) |
| RT4 | Testes que garantam a qualidade | Cobertura ≥ 80% por repositório, BDD da SAGA, contract tests e SonarCloud no CI |
| RT5 | CI/CD | GitHub Actions por repositório, credenciais da AWS Academy Learner Lab em GitHub Secrets e deploy automático na `main` |

## Entregáveis do enunciado

- Documentação da arquitetura proposta (este repositório).
- Script de criação do banco de dados e dos demais recursos (`fiapx-infra/sql` e Terraform).
- Links dos repositórios no GitHub.
- Vídeo de até 10 minutos com a documentação, a arquitetura e o projeto funcionando.

## Diagnóstico do projeto base

O projeto base é um único `main.go` (Go + Gin). A lógica de negócio que preservamos é esta:

```bash
ffmpeg -i <video> -vf fps=1 -y <tempDir>/frame_%04d.png   # extrai 1 frame por segundo
# compacta todos os frame_*.png em frames_<id>.zip
# formatos aceitos: mp4, avi, mov, mkv, wmv, flv, webm
```

| Problema no projeto base | Impacto | Como resolvemos |
|---|---|---|
| Processamento síncrono dentro do `POST /upload` | A requisição fica presa durante o `ffmpeg`; poucos uploads simultâneos derrubam o servidor | Upload direto ao S3 e processamento assíncrono por fila |
| Arquivos em disco local (`uploads/`, `outputs/`, `temp/`) | Não escala horizontalmente; perde tudo se o pod reiniciar | Amazon S3 para vídeos e zips; disco do pod só como área de trabalho temporária |
| Timestamp de segundos como identificador | Dois uploads no mesmo segundo colidem | UUID v7 gerado no domínio |
| Sem autenticação e com CORS `*` | Qualquer pessoa usa e baixa arquivos de outros | Cadastro e login com JWT; cada vídeo pertence a um usuário |
| `GET /api/status` lista o diretório `outputs/` | Não há status por vídeo nem histórico | Tabela `videos` com ciclo de vida e máquina de estados da SAGA |
| `GET /download/:filename` sem sanitização | Risco de path traversal | Download por URL pré-assinada do S3, só para o dono do vídeo |
| Sem testes, sem fila, sem tratamento de falha | Falhas silenciosas, nenhum aviso ao usuário | Testes unitários, BDD e de contrato; DLQ; SAGA com compensação e e-mail de falha |
| Dockerfile roda `go run` e `go mod tidy` na imagem final | Imagem grande, build não reprodutível | Dockerfiles multi-stage, usuário não-root, scan com Trivy |

## Escopo

**Dentro do escopo:** cadastro e login, recuperação e troca de senha, upload de vários vídeos, processamento assíncrono, listagem de
status, download do zip, e-mail de falha (e, opcionalmente, de conclusão), infraestrutura na AWS por
Terraform (numa conta da AWS Academy Learner Lab,
[ADR-019](../04-adrs/ADR-019-deploy-na-aws-academy-learner-lab.md)), CI/CD, observabilidade e teste de carga.

**Fora do escopo:** edição dos dados de perfil, compartilhamento de vídeos entre usuários,
escolha de outra taxa de frames pelo usuário e múltiplos ambientes além de `local` e `prod`.

## Visão da solução

A solução tem sete repositórios. Cada serviço é dono dos seus dados, e a comunicação entre eles é
assíncrona, por filas SQS com contratos JSON versionados.

| Repositório | Papel |
|---|---|
| `fiapx-docs` | Esta documentação |
| `fiapx-infra` | Infraestrutura compartilhada na AWS (Terraform) e ambiente local |
| `fiapx-auth` | Identidade: cadastro, login e validação do token |
| `fiapx-video-api` | Gestão de vídeos e orquestração da SAGA de processamento |
| `fiapx-video-processor` | Extração dos frames e geração do zip |
| `fiapx-notification` | Envio de e-mails e histórico de notificações |
| `fiapx-web` | Front-end |

Detalhes: [C4 de contexto](../03-arquitetura/c4-contexto.md),
[containers](../03-arquitetura/c4-containers.md) e [SAGA](../03-arquitetura/saga.md).

## Equipe

| Integrante | RM |
|---|---|
| Diego Fenille | rm372271 |
| Eduardo Santos | rm373573 |
