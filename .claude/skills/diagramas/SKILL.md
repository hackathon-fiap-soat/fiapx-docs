---
name: diagramas
description: Regras para criar ou alterar diagramas Mermaid no fiapx-docs e gerar as imagens PNG/SVG em diagramas/<assunto>/. Use sempre que um bloco ```mermaid for criado, alterado ou removido.
---

# Diagramas

Todo bloco Mermaid tem imagem gerada (PNG e SVG) em `diagramas/<assunto>/<nome>`, usada no PDF de entrega,
nos slides e no vídeo.

1. Escreva ou altere o bloco no Markdown de origem. Não use o layout ELK (o GitHub pode não renderizar).
2. Bloco novo: adicione a entrada no `CATALOGO` de `scripts/render-diagrams.py`, com a chave
   `(arquivo, posição do bloco no arquivo)` e o valor `(assunto, nome, título)`. Os assuntos, na ordem do
   roteiro do vídeo: `01-contexto`, `02-dominio`, `03-arquitetura`, `04-fluxos`, `05-saga`, `06-dados`,
   `07-seguranca-e-escala`, `08-deploy`, `09-observabilidade`. Inserir um bloco antes de outro no mesmo
   arquivo muda a posição dos seguintes: ajuste as chaves.
3. Gere: `python3 scripts/render-diagrams.py` (recria `diagramas/` inteira e o índice `diagramas/README.md`).
4. Abra o PNG gerado e confira se está legível. Diagrama grande demais fica ilegível no layout dagre:
   divida em dois (como o C4 de containers, síncrono e assíncrono).
5. Commite o Markdown, o script e as imagens no mesmo PR. O CI roda `--check` e falha se faltar entrada ou
   imagem.

Não duplique diagramas: um ADR que repetiria um diagrama da arquitetura referencia a imagem do diagrama
principal (`![...](../diagramas/<assunto>/<nome>.png)`) com link para a origem.
