# FAROL

**Fluxo de Atendimento, Resolução e Orientação em Laço**

Solução para o desafio da Seção de Coordenação de Educação a Distância: EMERON / TJRO.

> Responde antes da pergunta. E trabalha para nunca mais precisar responder.

---

## O que é

Uma camada de atendimento inteligente de três andares, entregue nos canais que já existem, cuja meta declarada é ser usada cada vez menos.

| Andar | O que faz |
|---|---|
| **Antecipar** | Detecta onde o participante travou e entrega a orientação certa antes da pergunta existir |
| **Resolver** | Responde sobre o caso individual da pessoa, ancorado em fonte oficial; recusa quando não sabe e escala com dossiê pronto |
| **Extinguir** | Descobre onde na jornada a dúvida nasce e emite ordens de correção da plataforma |

O princípio arquitetural é que **nenhuma ação termina no envio: toda ação termina na verificação do efeito**. O sistema avisa e confere se evitou o atendimento; responde e confere se resolveu; aponta a causa e confere se o volume caiu.

Detalhamento completo em [`farol-v2-documento-mestre.md`](./farol-v2-documento-mestre.md).

---

## Stack

| Camada | Escolha |
|---|---|
| Backend | FastAPI (Python 3.12) |
| Frontend | React + TypeScript + Tailwind |
| Banco | PostgreSQL 16 + pgvector |
| LLM | OpenAI, com fallback determinístico por palavras-chave |
| Embeddings | `text-embedding-3-small`, ou modelo local offline |

**Tecnologia deliberadamente ausente:** visão computacional, blockchain, IoT, geoprocessamento, fine-tuning. Nenhuma delas resolve este problema.

---

## Rodando

Pré-requisitos: Python 3.12+, Node 22+, Docker.

```bash
make setup     # instala dependências e cria o .env
# preencha OPENAI_API_KEY no .env
make dev       # sobe banco, API e front
```

- API: `http://localhost:8000`, estado do sistema em `/health`
- Front: `http://localhost:5173`

Outros alvos: `make migrate`, `make test`, `make lint`, `make reset`.

---

## Subindo em produção

Um host, um domínio, um comando. A imagem carrega o front construído dentro
da API, que o serve: **uma origem só**, sem CORS a liberar, sem URL de API para
configurar no build e com o WebSocket do espelho no mesmo certificado.

```bash
cp .env.producao.example .env.producao
make token            # gere um valor para FAROL_ADMIN_TOKEN e outro para FAROL_SAL_AUDITORIA
# preencha .env.producao (domínio, senha do banco, os dois tokens, OPENAI_API_KEY)
make prod             # constrói, migra e sobe: banco + API + TLS automático
make prod-seed        # uma vez, para popular o mundo fictício
```

Pré-requisitos: um host com Docker e um domínio já apontado para ele — o Caddy
emite e renova o certificado sozinho. `make prod-logs` acompanha, `make prod-parar`
derruba sem apagar o banco.

O que o `docker-compose.prod.yml` deliberadamente **não** faz: publicar a porta
do Postgres. O banco fala com a API pela rede interna e não tem porta aberta
para a internet. O único container exposto é o proxy, em 80 e 443.

Para uma demonstração rápida sem infraestrutura, `make dev` mais um túnel
(`cloudflared tunnel --url http://localhost:5173`) resolve — mas só enquanto a
máquina estiver ligada.

---

## Segurança

A chave do provedor de LLM nunca chega ao navegador, nunca entra no repositório
e nunca aparece inteira em log ou resposta de erro. O risco maior, porém, não é
o vazamento: é o **abuso**. Toda chamada de atendimento gasta crédito, e uma URL
pública sem defesa é um cartão aberto. As camadas, de fora para dentro:

| Camada | O que faz |
|---|---|
| **Partida** | Em `AMBIENTE=producao`, configuração insegura impede o processo de subir: sem token de administrador, com token curto ou com origem sem TLS, o FAROL não liga |
| **Superfície restrita** | Console de Demonstração e "Como o FAROL decide" exigem `X-Farol-Token`. A proteção está na inclusão do router, não rota a rota: rota nova nasce protegida |
| **Limite por origem** | 120 req/min no geral e 12/min nas rotas que falam com o provedor, contadas por origem para que um visitante abusivo não derrube o atendimento dos outros |
| **Teto de gasto** | Orçamento diário de chamadas ao provedor. Estourado, o motor **degrada para o fallback determinístico** em vez de derrubar o serviço ou zerar o crédito, e o `/health` conta a verdade |
| **Trilha de auditoria** | Toda requisição que muda estado entra no log append-only com ator, rota, resultado e duração. As recusas por excesso e as tentativas com token inválido entram também |
| **Navegador** | CORS de lista fechada, `nosniff`, `X-Frame-Options`, HSTS em produção, `/docs` desativada em produção e nenhum *traceback* devolvido ao cliente |
| **Webhook** | Com `WHATSAPP_APP_SECRET` definido, só passa payload assinado pela Meta (`X-Hub-Signature-256`) |

**O ator da auditoria não guarda dado pessoal.** O IP entra como hash truncado
com sal: a trilha preserva o que precisa (distinguir e correlacionar atores) e
descarta o que não precisa (identificar a pessoa). LGPD por construção.

**O portão no front é conveniência, não proteção.** Quem autoriza é o servidor,
a cada requisição; a tela só evita mostrar uma superfície quebrada a quem não
tem acesso. O token fica em `sessionStorage`, some quando a aba fecha e nunca
viaja pela URL.

Em desenvolvimento, `FAROL_ADMIN_TOKEN` vazio deixa as duas superfícies abertas
na máquina local — de propósito: exigir segredo para rodar `make dev` empurraria
a equipe a inventar um token fraco e fixo, que é pior do que não ter.

---

## Decisões que valem explicação

**O canal WhatsApp é uma réplica de interface, não a API oficial.** Ela fala com o backend pelo mesmo contrato de adaptador que a Cloud API usaria, recebendo payloads em formato de webhook. Trocar em produção é registrar outra implementação: a camada não é um atalho, é a arquitetura correta com implementação trocável.

**O log de auditoria é imutável no banco, não por convenção.** Um trigger recusa `UPDATE` e `DELETE`. Rastreabilidade é requisito não negociável em ambiente judiciário, e disciplina de código não é garantia.

**A decisão de escalar não é tomada por IA.** A política de triagem é uma tabela determinística e auditável. Categoria sensível escala sempre, independentemente da confiança. Onde IA não é necessária, não é usada.

**Sem fonte válida e vigente, o sistema não responde.** Conhecimento vencido escala para humano. Uma resposta desatualizada com carimbo institucional é pior que nenhuma resposta, porque carrega a autoridade da Escola.

**Os dados são 100% fictícios**, conforme a regra do desafio.
