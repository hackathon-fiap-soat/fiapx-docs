#!/usr/bin/env python3
"""Gera PNG e SVG de todos os diagramas Mermaid da documentação, organizados por assunto em diagramas/.

Uso: python3 scripts/render-diagrams.py           gera as imagens (precisa de Node.js)
     python3 scripts/render-diagrams.py --check   só confere se todo bloco está no CATALOGO e tem imagem
Variável opcional PUPPETEER_CFG: caminho de um JSON de configuração do Puppeteer (ex.: --no-sandbox no CI).

Cada bloco ```mermaid é identificado pelo arquivo de origem e pela sua posição no arquivo (1, 2, ...).
Todo bloco precisa estar no CATALOGO: um diagrama novo sem entrada faz o script falhar, para que alguém
decida em qual assunto ele entra e com qual nome.
"""
import os, re, subprocess, sys, shutil, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "diagramas")
MMDC = ["npx", "-y", "@mermaid-js/mermaid-cli@11.4.2"]

# Assuntos na ordem de leitura (a mesma do roteiro do vídeo).
ASSUNTOS = [
    ("01-contexto", "Contexto"),
    ("02-dominio", "Domínio (Domain Storytelling)"),
    ("03-arquitetura", "Arquitetura"),
    ("04-fluxos", "Fluxos (sequências)"),
    ("05-saga", "SAGA"),
    ("06-dados", "Dados"),
    ("07-seguranca-e-escala", "Segurança, escala e e-mail"),
    ("08-deploy", "Deploy"),
    ("09-observabilidade", "Observabilidade"),
]

# (arquivo de origem, posição do bloco) -> (assunto, nome do arquivo, título)
CATALOGO = {
    ("01-contexto/linguagem-ubiqua.md", 1): ("01-contexto", "mapa-de-contextos", "Mapa de contextos (bounded contexts)"),
    ("03-arquitetura/c4-contexto.md", 1): ("01-contexto", "c4-contexto", "C4 nível 1: contexto do sistema"),
    ("02-domain-storytelling/ds-01-cadastro-e-login.md", 1): ("02-dominio", "ds-01-cadastro-e-login", "DS-01 Cadastro e login"),
    ("02-domain-storytelling/ds-02-envio-de-video.md", 1): ("02-dominio", "ds-02-envio-de-video", "DS-02 Envio de vídeo"),
    ("02-domain-storytelling/ds-03-processamento-com-sucesso.md", 1): ("02-dominio", "ds-03-processamento-com-sucesso", "DS-03 Processamento com sucesso"),
    ("02-domain-storytelling/ds-04-falha-e-notificacao.md", 1): ("02-dominio", "ds-04-falha-e-notificacao", "DS-04 Falha e notificação"),
    ("02-domain-storytelling/ds-05-consulta-status-e-download.md", 1): ("02-dominio", "ds-05-consulta-status-e-download", "DS-05 Consulta de status e download"),
    ("02-domain-storytelling/ds-06-recuperacao-e-troca-de-senha.md", 1): ("02-dominio", "ds-06-recuperacao-e-troca-de-senha", "DS-06 Recuperação e troca de senha"),
    ("03-arquitetura/c4-containers.md", 1): ("03-arquitetura", "c4-containers-sincrono", "C4 nível 2: caminho síncrono (navegador, autenticação e API)"),
    ("03-arquitetura/c4-containers.md", 2): ("03-arquitetura", "c4-containers-assincrono", "C4 nível 2: processamento assíncrono (SAGA, worker e notificação)"),
    ("03-arquitetura/c4-componentes-video-api.md", 1): ("03-arquitetura", "c4-componentes-video-api", "C4 nível 3: componentes do fiapx-video-api"),
    ("04-adrs/ADR-003-ddd-e-clean-architecture-nos-servicos-laravel.md", 1): ("03-arquitetura", "camadas-clean-architecture", "Camadas DDD + Clean Architecture (ADR-003)"),
    ("04-adrs/ADR-010-api-gateway-vpc-link-alb-interno-e-targetgroupbinding.md", 1): ("03-arquitetura", "exposicao-da-api", "Exposição da API: API Gateway, VPC Link e ALB interno (ADR-010)"),
    ("04-adrs/ADR-001-polyrepo-e-integracao-via-ssm-parameter-store.md", 1): ("03-arquitetura", "integracao-via-ssm", "Integração entre repositórios via SSM Parameter Store (ADR-001)"),
    ("03-arquitetura/sequencias.md", 1): ("04-fluxos", "seq-01-cadastro-e-login", "Sequência 1: cadastro e login"),
    ("03-arquitetura/sequencias.md", 2): ("04-fluxos", "seq-02-upload-e-processamento", "Sequência 2: upload e processamento com sucesso"),
    ("03-arquitetura/sequencias.md", 3): ("04-fluxos", "seq-03-falha-e-compensacao", "Sequência 3: falha no processamento com compensação"),
    ("03-arquitetura/sequencias.md", 4): ("04-fluxos", "seq-03b-timeout", "Sequência 3b: timeout do processamento"),
    ("03-arquitetura/sequencias.md", 5): ("04-fluxos", "seq-04-consulta-e-download", "Sequência 4: consulta e download"),
    ("03-arquitetura/sequencias.md", 6): ("04-fluxos", "seq-05-recuperacao-e-troca-de-senha", "Sequência 5: recuperação e troca de senha"),
    ("04-adrs/ADR-013-notificacao-sqs-lambda-ses-e-historico-no-dynamodb.md", 1): ("04-fluxos", "fluxo-de-notificacao", "Fluxo de notificação: SQS, Lambda, DynamoDB e SES (ADR-013)"),
    ("03-arquitetura/saga.md", 1): ("05-saga", "estados-da-saga", "Estados da saga"),
    ("03-arquitetura/modelo-de-dados.md", 1): ("06-dados", "modelo-er", "Modelo ER: fiapx_auth e fiapx_video"),
    ("04-adrs/ADR-005-aurora-mysql-serverless-v2-um-database-por-servico.md", 1): ("06-dados", "cluster-aurora", "Cluster Aurora com um database por serviço (ADR-005)"),
    ("03-arquitetura/seguranca.md", 1): ("07-seguranca-e-escala", "rede-e-seguranca", "Rede e segurança"),
    ("03-arquitetura/escalabilidade-e-resiliencia.md", 1): ("07-seguranca-e-escala", "escala-keda", "Escala do worker pelo KEDA"),
    ("04-adrs/ADR-015-remetente-de-email-dominio-proprio-e-sandbox-do-ses.md", 1): ("07-seguranca-e-escala", "remetente-de-email-ses", "Remetente de e-mail: domínio, DKIM e SES (ADR-015)"),
    ("06-deploy/fluxo-de-deploy.md", 1): ("08-deploy", "pipelines", "Pipelines por tipo de repositório"),
    ("06-deploy/fluxo-de-deploy.md", 2): ("08-deploy", "ordem-de-deploy", "Ordem de deploy entre repositórios (primeira subida)"),
    ("04-adrs/ADR-016-terraform-apply-somente-via-github-actions.md", 1): ("08-deploy", "politica-terraform-apply", "Política de terraform apply (ADR-016)"),
    ("07-observabilidade/observabilidade.md", 1): ("09-observabilidade", "fluxo-de-telemetria", "Fluxo de telemetria para o New Relic"),
}


def blocos():
    for md in sorted(glob.glob("**/*.md", recursive=True)):
        if md.startswith(("diagramas/", "node_modules/", ".mermaid-check/")):
            continue
        texto = open(md, encoding="utf-8").read()
        for i, m in enumerate(re.finditer(r"^```mermaid\n(.*?)^```", texto, re.S | re.M), 1):
            yield md, i, m.group(1)


def main():
    os.chdir(ROOT)
    achados = list(blocos())
    sem_catalogo = [(md, i) for md, i, _ in achados if (md, i) not in CATALOGO]
    sobrando = [k for k in CATALOGO if k not in {(md, i) for md, i, _ in achados}]
    if sem_catalogo or sobrando:
        for md, i in sem_catalogo:
            print(f"ERRO  bloco sem entrada no CATALOGO: {md} (bloco {i})")
        for md, i in sobrando:
            print(f"ERRO  entrada do CATALOGO sem bloco correspondente: {md} (bloco {i})")
        sys.exit(1)
    if "--check" in sys.argv:
        faltando = [f"{a}/{n}.{e}" for a, n, _ in CATALOGO.values() for e in ("png", "svg")
                    if not os.path.exists(os.path.join(OUT, a, f"{n}.{e}"))]
        for f in faltando:
            print(f"ERRO  imagem não gerada: diagramas/{f} (rode python3 scripts/render-diagrams.py)")
        print(f"{len(achados)} diagramas no catálogo; {len(faltando)} imagens faltando.")
        sys.exit(1 if faltando else 0)

    shutil.rmtree(OUT, ignore_errors=True)
    tmp = os.path.join(OUT, "_src")
    os.makedirs(tmp)
    cfg = os.environ.get("PUPPETEER_CFG")
    falha = 0
    for md, i, codigo in achados:
        assunto, nome, _ = CATALOGO[(md, i)]
        os.makedirs(os.path.join(OUT, assunto), exist_ok=True)
        src = os.path.join(tmp, f"{assunto}--{nome}.mmd")
        open(src, "w", encoding="utf-8").write(codigo)
        for ext, extra in (("svg", []), ("png", ["-s", "2", "-b", "white"])):
            destino = os.path.join(OUT, assunto, f"{nome}.{ext}")
            cmd = MMDC + ["-q", "-i", src, "-o", destino] + extra + (["-p", cfg] if cfg else [])
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                falha = 1
                print(f"ERRO  {assunto}/{nome}.{ext}\n{r.stderr[-600:]}")
        print(f"ok    {assunto}/{nome}")
    shutil.rmtree(tmp)

    linhas = [
        "# Imagens dos diagramas",
        "",
        "Imagens geradas a partir dos blocos Mermaid da documentação, organizadas por assunto e na ordem de",
        "leitura, para usar no documento de entrega, em slides e no vídeo. **Não edite estes arquivos à mão**:",
        "altere o diagrama no Markdown de origem e rode `python3 scripts/render-diagrams.py`.",
        "",
        f"Total: {len(achados)} diagramas, cada um em PNG (escala 2x, fundo branco) e SVG.",
    ]
    origem = {v[:2]: k[0] for k, v in CATALOGO.items()}
    for assunto, titulo in ASSUNTOS:
        itens = [v for v in CATALOGO.values() if v[0] == assunto]
        if not itens:
            continue
        linhas += ["", f"## {titulo}", "", "| Diagrama | Imagens | Origem |", "|---|---|---|"]
        for _, nome, tit in sorted(itens, key=lambda v: v[1]):
            md = origem[(assunto, nome)]
            linhas.append(f"| {tit} | [PNG]({assunto}/{nome}.png) · [SVG]({assunto}/{nome}.svg) | [`{md}`](../{md}) |")
    open(os.path.join(OUT, "README.md"), "w", encoding="utf-8").write("\n".join(linhas) + "\n")
    print(f"{len(achados)} diagramas gerados em diagramas/")
    sys.exit(falha)


if __name__ == "__main__":
    main()
