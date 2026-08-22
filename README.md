<div align="center">

# 🔦 FAROL

**Fluxo de Atendimento, Resolução e Orientação em Laço**

*Responde antes da pergunta. E trabalha para nunca mais precisar responder.*

Solução para o desafio da Seção de Coordenação de Educação a Distância — **EMERON / TJRO**

<br>

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL_16_+_pgvector-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)

</div>

---

## Índice

- [O que é](#o-que-é)
- [Stack](#stack)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Rodando localmente](#rodando-localmente)
- [Subindo em produção](#subindo-em-produção)
- [Segurança](#segurança)
- [Decisões que valem explicação](#decisões-que-valem-explicação)

---

## O que é

Uma camada de atendimento inteligente de **três andares**, entregue nos canais que já existem, cuja meta declarada é ser usada cada vez menos.

<table>
<tr>
<th align="left" width="140">Andar</th>
<th align="left">O que faz</th>
</tr>
<tr>
<td><b>🎯 Antecipar</b></td>
<td>Detecta onde o participante travou e entrega a orientação certa <i>antes</i> da pergunta existir</td>
</tr>
<tr>
<td><b>💬 Resolver</b></td>
<td>Responde sobre o caso individual da pessoa, ancorado em fonte oficial; recusa quando não sabe e escala com dossiê pronto</td>
</tr>
<tr>
<td><b>🧹 Extinguir</b></td>
<td>Descobre onde na jornada a dúvida nasce e emite ordens de correção da plataforma</td>
</tr>
</table>

> [!IMPORTANT]
> O princípio arquitetural é que **nenhuma ação termina no envio: toda ação termina na verificação do efeito.**
> O sistema avisa e confere se evitou o atendimento; responde e confere se resolveu; aponta a causa e confere se o volume caiu.

📖 Detalhamento completo em [`farol-v2-documento-mestre.md`](./farol-v2-documento-mestre.md).

---

## Stack

| Camada | Escolha |
|:--|:--|
| **Backend** | FastAPI (Python 3.12) |
| **Frontend** | React + TypeScript + Tailwind |
| **Banco** | PostgreSQL 16 + pgvector |
| **LLM** | OpenAI, com fallback determinístico por palavras-chave |
| **Embeddings** | `text-embedding-3-small`, ou modelo local offline |

> [!NOTE]
> **Tecnologia deliberadamente ausente:** visão computacional, blockchain, IoT, geoprocessamento, fine-tuning.
> Nenhuma delas resolve este problema.

---

## Estrutura do repositório

```
.
├── apps/
│   ├── api/                 # FastAPI — motor, canais, gatilhos e políticas
│   │   ├── app/
│   │   │   ├── api/         # rotas HTTP e WebSocket
│   │   │   ├── channels/    # adaptadores de canal (WhatsApp, AVA)
│   │   │   ├── gatilhos/    # detecção de travamento e antecipação
│   │   │   ├── llm/         # provedor, fallback determinístico e orçamento
│   │   │   ├── seed/        # mundo fictício da demonstração
│   │   │   ├── services/    # triagem, resposta ancorada, auditoria
│   │   │   └── seguranca.py # tokens, limites e trilha de auditoria
│   │   ├── alembic/         # migrations
│   │   └── tests/
│   └── web/                 # React + Vite — console, espelho e painéis
│       └── src/
├── infra/                   # Dockerfile, compose (dev e prod), Caddy
├── render.yaml              # blueprint de deploy no Render
└── Makefile                 # todos os comandos do projeto
```

---

## Rodando localmente

**Pré-requisitos:** Python 3.12+, Node 22+, Docker.

```bash
make setup     # instala dependências e cria o .env
#              ↳ preencha OPENAI_API_KEY no .env
make dev       # sobe banco, API e front
```

| Serviço | URL |
|:--|:--|
| 🖥️ Front | `http://localhost:5173` |
| ⚙️ API | `http://localhost:8000` |
| ❤️ Estado do sistema | `http://localhost:8000/health` |

<details>
<summary><b>Outros comandos do Makefile</b></summary>

<br>

| Comando | O que faz |
|:--|:--|
| `make migrate` | Aplica as migrations |
| `make revision m="…"` | Gera migration a partir dos models |
| `make seed` | Popula o banco com o mundo fictício |
| `make api` / `make web` | Sobe só a API / só o front |
| `make test` | Roda os testes |
| `make lint` | Roda o linter |
| `make reset` | Apaga o banco, recria e repopula |
| `make token` | Gera um token forte para `FAROL_ADMIN_TOKEN` / `FAROL_SAL_AUDITORIA` |

</details>

---

## Subindo em produção

### 🚀 Render — plano gratuito, sem cartão e sem domínio próprio

O repositório traz um `render.yaml`: o Render lê o arquivo e cria os dois serviços sozinho.

1. Em [render.com](https://render.com) → **New** → **Blueprint** → conecte este repositório.
2. Preencha as duas variáveis que ele pedir: `OPENAI_API_KEY` e `WEB_ORIGIN` (a URL que o Render acabou de dar, com `https://`).
3. Espere o primeiro deploy. As migrations rodam na partida e o mundo fictício é semeado uma única vez — a semeadura confere se o banco está vazio antes.
4. Pegue o `FAROL_ADMIN_TOKEN` em **Environment**: o Render o gerou sozinho, e é ele que abre o Console e a tela "Como decide".

O Render devolve um link estável, com HTTPS incluso, no formato `https://<nome-do-servico>.onrender.com`.

> [!NOTE]
> **O ambiente usado na apresentação foi desligado.** O blueprint continua no repositório: subir de novo é reconectar o `render.yaml` e refazer os quatro passos acima.

> [!WARNING]
> **A contrapartida do plano gratuito:** o serviço adormece após 15 minutos sem acesso e o primeiro acesso seguinte leva ~50 segundos para responder — abra o link alguns minutos antes de apresentar. O Postgres gratuito também expira em 30 dias: basta para o hackathon, não serve para operação real.

### 🏠 Um host próprio

Um host, um domínio, um comando. A imagem carrega o front construído dentro da API, que o serve: **uma origem só**, sem CORS a liberar, sem URL de API para configurar no build e com o WebSocket do espelho no mesmo certificado.

```bash
cp .env.producao.example .env.producao
make token            # gere FAROL_ADMIN_TOKEN e FAROL_SAL_AUDITORIA
#                     ↳ preencha .env.producao (domínio, senha do banco,
#                       os dois tokens e OPENAI_API_KEY)
make prod             # constrói, migra e sobe: banco + API + TLS automático
make prod-seed        # uma vez, para popular o mundo fictício
```

**Pré-requisitos:** um host com Docker e um domínio já apontado para ele — o Caddy emite e renova o certificado sozinho.
`make prod-logs` acompanha; `make prod-parar` derruba sem apagar o banco.

> [!NOTE]
> O que o `docker-compose.prod.yml` deliberadamente **não** faz: publicar a porta do Postgres. O banco fala com a API pela rede interna e não tem porta aberta para a internet. O único container exposto é o proxy, em 80 e 443.

<details>
<summary><b>Demonstração rápida, sem infraestrutura</b></summary>

<br>

`make dev` mais um túnel resolve — mas só enquanto a máquina estiver ligada:

```bash
cloudflared tunnel --url http://localhost:5173
```

</details>

---

## Segurança

A chave do provedor de LLM nunca chega ao navegador, nunca entra no repositório e nunca aparece inteira em log ou resposta de erro. O risco maior, porém, não é o vazamento: é o **abuso**. Toda chamada de atendimento gasta crédito, e uma URL pública sem defesa é um cartão aberto.

As camadas, de fora para dentro:

| Camada | O que faz |
|:--|:--|
| 🔌 **Partida** | Em `AMBIENTE=producao`, configuração insegura impede o processo de subir: sem token de administrador, com token curto ou com origem sem TLS, o FAROL não liga |
| 🚪 **Superfície restrita** | Console de Demonstração e "Como o FAROL decide" exigem `X-Farol-Token`. A proteção está na inclusão do router, não rota a rota: **rota nova nasce protegida** |
| 🚦 **Limite por origem** | 120 req/min no geral e 12/min nas rotas que falam com o provedor, contadas por origem para que um visitante abusivo não derrube o atendimento dos outros |
| 💸 **Teto de gasto** | Orçamento diário de chamadas ao provedor. Estourado, o motor **degrada para o fallback determinístico** em vez de derrubar o serviço ou zerar o crédito, e o `/health` conta a verdade |
| 📜 **Trilha de auditoria** | Toda requisição que muda estado entra no log append-only com ator, rota, resultado e duração. As recusas por excesso e as tentativas com token inválido entram também |
| 🌐 **Navegador** | CORS de lista fechada, `nosniff`, `X-Frame-Options`, HSTS em produção, `/docs` desativada em produção e nenhum *traceback* devolvido ao cliente |
| 🔗 **Webhook** | Com `WHATSAPP_APP_SECRET` definido, só passa payload assinado pela Meta (`X-Hub-Signature-256`) |

**O ator da auditoria não guarda dado pessoal.** O IP entra como hash truncado com sal: a trilha preserva o que precisa (distinguir e correlacionar atores) e descarta o que não precisa (identificar a pessoa). **LGPD por construção.**

**O portão no front é conveniência, não proteção.** Quem autoriza é o servidor, a cada requisição; a tela só evita mostrar uma superfície quebrada a quem não tem acesso. O token fica em `sessionStorage`, some quando a aba fecha e nunca viaja pela URL.

> [!TIP]
> Em desenvolvimento, `FAROL_ADMIN_TOKEN` vazio deixa as duas superfícies abertas na máquina local — de propósito: exigir segredo para rodar `make dev` empurraria a equipe a inventar um token fraco e fixo, que é pior do que não ter.

---

## Decisões que valem explicação

<details open>
<summary><b>O canal WhatsApp é uma réplica de interface, não a API oficial</b></summary>

Ela fala com o backend pelo mesmo contrato de adaptador que a Cloud API usaria, recebendo payloads em formato de webhook. Trocar em produção é registrar outra implementação: a camada não é um atalho, é a arquitetura correta com implementação trocável.

</details>

<details open>
<summary><b>O log de auditoria é imutável no banco, não por convenção</b></summary>

Um trigger recusa `UPDATE` e `DELETE`. Rastreabilidade é requisito não negociável em ambiente judiciário, e disciplina de código não é garantia.

</details>

<details open>
<summary><b>A decisão de escalar não é tomada por IA</b></summary>

A política de triagem é uma tabela determinística e auditável. Categoria sensível escala sempre, independentemente da confiança. Onde IA não é necessária, não é usada.

</details>

<details open>
<summary><b>Sem fonte válida e vigente, o sistema não responde</b></summary>

Conhecimento vencido escala para humano. Uma resposta desatualizada com carimbo institucional é pior que nenhuma resposta, porque carrega a autoridade da Escola.

</details>

---

<div align="center">

**Os dados são 100% fictícios**, conforme a regra do desafio.

</div>
