# sync_relay

[English](README.md) | Português | [Español](README.es.md)

![License: MIT](https://img.shields.io/badge/license-MIT-blue) ![Version 0.1.2](https://img.shields.io/badge/version-0.1.2-informational) ![CLI: Claude Code | Codex (untested)](https://img.shields.io/badge/CLI-Claude%20Code%20%7C%20Codex%20(n%C3%A3o%20testado)-lightgrey)

Mantém a sessão principal só na orquestração, manda o trabalho para subagentes e passa uma sessão longa para uma nova, com um arquivo de passagem, antes de o contexto ficar caro.

## Instalação

Claude Code:

```sh
claude plugin marketplace add Sync-Labs-team/sync_relay
claude plugin install sync_relay@sync_relay
```

Codex (não testado numa sessão real, veja [CLIs suportadas](#clis-suportadas)):

```sh
codex plugin marketplace add Sync-Labs-team/sync_relay
codex plugin add sync_relay@sync_relay
```

Precisa de Python 3.9 ou mais novo como `python3`. No Claude Code o mesmo plugin também acrescenta o comando `/relay`, um botão e uma linha de estado. Atualização, remoção e problemas comuns: [docs/faq.md](docs/faq.md) (em inglês).

## Destaques

- A sessão principal só orquestra: leitura, busca, shell, escrita, web e MCP vão para um subagente, conforme uma tabela de delegação que você pode editar. `claude -p` e `codex exec` nunca são bloqueados.
- Uma palavra, `relay`, grava o estado do trabalho num arquivo, e a próxima sessão na mesma pasta começa com ele. O arquivo leva o seu `/goal`, as tarefas agendadas e o trabalho em segundo plano, que o `/clear` apagaria ou deixaria solto.
- O ponto de troca automático segue a janela do modelo: 180k tokens numa janela de 1M do Claude, 166k em 200K, 102k num limite de 120k do Codex (primeira resposta em 30k tokens). Regra: [docs/how-it-works.md](docs/how-it-works.md).
- O gancho custa cerca de 196 ms por chamada no Windows com o atalho `python3` da Microsoft Store, e cerca de 26 ms de interpretador com o Python do python.org.
- 0 chamadas de rede. Tudo fica no seu perfil de usuário. O texto da passagem é limitado a 9.000 caracteres.
- 90 testes dos ganchos e do script, 182 do mod do Claude Code.

## Início rápido

1. Instale o plugin (acima) e abra uma sessão como de costume. A sessão principal passa a delegar.
2. Quando o contexto crescer, digite a palavra `relay` sozinha na mensagem (no Claude Code, `/relay` também funciona). O modelo grava a passagem.
3. Digite `/clear` (no Codex, `/new`). A sessão nova começa com a passagem.

No Claude Code, `/relay` faz os passos 2 e 3 por você, e `/relay auto` faz sozinho no ponto de troca.

## Comandos

| Comando | O que faz |
|---|---|
| `/relay` | Grava a passagem e abre a sessão nova agora (Claude Code). |
| `/relay auto` | Liga ou desliga a troca automática. Lembra entre sessões. |
| `/relay button` | Mostra ou esconde o botão fixo `sync_relay auto: ligado/desligado` (en: `on/off`). Lembra entre sessões. A linha de estado fica. |
| `/relay status` | Modo da trava, auto, contexto atual, ponto de troca e a origem dele, pasta das passagens. |
| `relay` | A mensagem inteira. Igual a `/relay`, e é o jeito no Codex (depois `/new`). |

Qualquer outro argumento mostra o uso. A linha de estado, ao lado da sua, fica assim: `sync_relay: auto desligado · 45k de 150k` (ou `medindo`, `trocando…`).

## CLIs suportadas

| CLI | Situação |
|---|---|
| Claude Code 2.1.323 ou mais novo | Testado no Windows, versões 2.1.328 e 2.1.329. Ganchos e mod. |
| Codex CLI 0.170.0 | Instala, e o gancho foi rodado direto, sem modelo. Não testado numa sessão real. Só os ganchos (o mod é ignorado). Aprove os ganchos em `/hooks`. |
| macOS e Linux | Não testados. |

## Configuração

Um arquivo JSON para as duas CLIs: `%APPDATA%\sync_relay\config.json` no Windows, `~/.config/sync_relay/config.json` nos outros. Toda chave é opcional. Todas as chaves, padrões e variáveis de ambiente: [docs/configuration.md](docs/configuration.md) (em inglês).

| Chave | Padrão | O que faz |
|---|---|---|
| `mode` | `enforce` | `enforce` bloqueia ferramentas de trabalho na sessão principal, `remind` só lembra, `off` não faz nenhum dos dois. |
| `threshold_tokens` | `150000` | Teto do crescimento que dispara a troca. |
| `button` | `true` | Mostrar o botão fixo (Claude Code). |
| `auto` | `false` | Começar com a troca automática ligada (Claude Code). |
| `lang` | `auto` | `auto`, `en` ou `pt-BR`. |
| `handoff_dir` | por usuário | Onde ficam os arquivos de passagem. |
| `routing` | veja os docs | Agente, modelo e esforço por camada e por CLI. |

Para desligar numa sessão, abra a CLI com `SYNC_RELAY_MODE=off`.

## Como funciona

```mermaid
flowchart LR
  A[Sessão principal] -->|ferramentas de trabalho negadas| B[Subagente]
  A -->|relay| C[Arquivo de passagem]
  C -->|/clear ou /new| D[Sessão nova]
```

1. O `PreToolUse` nega ferramentas de trabalho na sessão principal interativa. Subagentes e automação passam.
2. No início da sessão, o plugin injeta uma tabela de delegação montada a partir da sua configuração.
3. `relay` pede ao modelo uma passagem em Markdown, gravada numa pasta do seu perfil de usuário.
4. No ponto de troca, o gancho `Stop` (ou o mod) avisa que é hora de trocar. A próxima sessão na mesma pasta recebe o arquivo uma vez.
5. A troca espera os subagentes que ainda não reportaram.

Regras, privacidade e medições: [docs/how-it-works.md](docs/how-it-works.md) (em inglês).

## Contribuição

Relatos de bug, ideias e perguntas entram por [issues](https://github.com/Sync-Labs-team/sync_relay/issues/new/choose). Pull requests de fora não são aceitos. Veja [CONTRIBUTING.md](CONTRIBUTING.md).

## Segurança

Relate vulnerabilidades em particular, pelos avisos de segurança do repositório: [SECURITY.md](SECURITY.md).

## Licença

MIT: [LICENSE](LICENSE). Notas de versão: [CHANGELOG.md](CHANGELOG.md).
