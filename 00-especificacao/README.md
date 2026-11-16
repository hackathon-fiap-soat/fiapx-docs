# Especificação do projeto

| Documento | Conteúdo |
|---|---|
| [`Projeto-hackton.md`](Projeto-hackton.md) | Especificação completa do time: requisitos, decisões fechadas, arquitetura, SAGA, mensageria, especificação por repositório, banco de dados, CI/CD, plano em etapas (§12), regras para o agente (§13) e checklist de entrega (§14) |
| [`Prompt-layout-web.md`](Prompt-layout-web.md) | Prompt usado para gerar o layout do `fiapx-web` no Google Stitch, com os contratos e regras de UX das telas |

A especificação é a fonte da verdade do plano e das regras. Os documentos das outras pastas detalham cada
assunto e, quando há conflito, valem as decisões mais recentes registradas em ADR.

Os diagramas Mermaid da especificação repetem os da arquitetura; as imagens são geradas a partir dos
documentos de origem (`diagramas/`), não daqui. Caminhos como `/Applications/XAMPP/...` e o PDF do enunciado
se referem à máquina de quem escreveu a especificação e não estão versionados.

Na pasta de trabalho local (a pasta que contém os repositórios `fiapx-*`), `Projeto-hackton.md` e
`Prompt-layout-web.md` são links simbólicos para estes arquivos: há uma única cópia.
