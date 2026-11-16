---
name: novo-adr
description: Cria um ADR novo no fiapx-docs no formato MADR usado pelo time, atualiza o índice e as referências. Use ao registrar qualquer decisão nova ou que contrarie uma decisão existente.
---

# Novo ADR

1. Próximo número: veja a tabela em `04-adrs/README.md`. Arquivo:
   `04-adrs/ADR-NNN-titulo-em-kebab-case.md`.
2. Estrutura (copie de um ADR recente, como o ADR-017 ou o ADR-018):

   ```markdown
   # ADR-NNN — Título

   - **Status:** Aceito
   - **Data:** AAAA-MM-DD
   - **Decisores:** Diego Fenille, Eduardo Santos
   - **Relacionados:** [ADR-XXX](ADR-XXX-....md)

   ## Contexto
   ## Decisão
   ## Alternativas consideradas   (tabela: Alternativa | Por que não)
   ## Consequências
   ### Positivas
   ### Negativas / riscos
   ### Mitigações
   ```

3. Se a decisão substitui outra, o ADR antigo passa a "Substituído por ADR-NNN" (não apague).
4. Atualize:
   - a tabela de `04-adrs/README.md`;
   - os documentos afetados (`03-arquitetura/`, `06-deploy/`, `contracts/`, `api/openapi.yaml`) e links
     cruzados nos ADRs relacionados;
   - na especificação `00-especificacao/Projeto-hackton.md`, a lista de ADRs e as contagens ("N ADRs" na
     Etapa 1 e no checklist do §14), e o total no índice do `README.md`.
5. Diagrama no ADR: siga a skill `diagramas`. Se ele repetiria um diagrama existente, referencie a imagem.
6. Valide com a skill `validar-docs` e abra o PR com a skill `fiapx-pr`.
7. Comunique a decisão ao time no relatório final.
