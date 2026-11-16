# Domain Storytelling

Seis histórias descrevem, na linguagem do negócio, como as pessoas e os sistemas colaboram na
plataforma FIAP X. Elas foram a base para identificar os bounded contexts e a linguagem ubíqua.

| # | História | Bounded contexts envolvidos |
|---|---|---|
| 1 | [Cadastro e login](ds-01-cadastro-e-login.md) | Identidade |
| 2 | [Envio de vídeo](ds-02-envio-de-video.md) | Identidade, Gestão de Vídeos |
| 3 | [Processamento com sucesso](ds-03-processamento-com-sucesso.md) | Gestão de Vídeos, Processamento |
| 4 | [Falha e notificação](ds-04-falha-e-notificacao.md) | Gestão de Vídeos, Processamento, Notificação |
| 5 | [Consulta de status e download](ds-05-consulta-status-e-download.md) | Identidade, Gestão de Vídeos |
| 6 | [Recuperação e troca de senha](ds-06-recuperacao-e-troca-de-senha.md) | Identidade, Notificação |

## Notação

Cada história é uma sequência numerada de frases no formato:

```text
<nº> <Ator> --<atividade>--> <Objeto de trabalho> --para/com--> <Ator>
```

O diagrama Mermaid de cada arquivo desenha a mesma sequência: atores como nós retangulares, objetos de
trabalho como nós arredondados e o número da frase no rótulo da seta.

**Atores:** Usuário, Plataforma FIAP X, Serviço de Identidade, Armazenamento, Fila, Processador e
Serviço de Notificação.

**Objetos de trabalho:** Credencial, Token, Vídeo, Cota, Pedido de processamento, Frames, Pacote zip,
Link de download e E-mail.

## Egon.io

As histórias também podem ser desenhadas no [Egon.io](https://egon.io), a ferramenta de Domain
Storytelling usada pelo time na Fase 1. Para isso:

1. Abra <https://egon.io/app> no navegador.
2. Crie os atores e objetos de trabalho com os nomes acima e ligue-os na ordem numerada da história.
3. Exporte em `.egn` (para editar depois) e `.svg` (para a documentação) e salve nesta pasta com o
   mesmo nome do arquivo Markdown, por exemplo `ds-02-envio-de-video.egn`.

Os arquivos `.egn` e `.svg` são opcionais: o texto e o diagrama Mermaid já descrevem cada história.
