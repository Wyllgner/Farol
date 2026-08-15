# FAROL

**Fluxo de Atendimento, Resolução e Orientação em Laço**

Solução para o desafio da Seção de Coordenação de Educação a Distância — EMERON / TJRO.

> Responde antes da pergunta. E trabalha para nunca mais precisar responder.

---

## O que é

Uma camada de atendimento inteligente de três andares, entregue nos canais que já existem, cuja meta declarada é ser usada cada vez menos.

| Andar | O que faz |
|---|---|
| **Antecipar** | Detecta onde o participante travou e entrega a orientação certa antes da pergunta existir |
| **Resolver** | Responde sobre o caso individual da pessoa, ancorado em fonte oficial; recusa quando não sabe e escala com dossiê pronto |
| **Extinguir** | Descobre onde na jornada a dúvida nasce e emite ordens de correção da plataforma |

O princípio arquitetural é que **nenhuma ação termina no envio — toda ação termina na verificação do efeito**. O sistema avisa e confere se evitou o atendimento; responde e confere se resolveu; aponta a causa e confere se o volume caiu.

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

- API: `http://localhost:8000` — estado do sistema em `/health`
- Front: `http://localhost:5173`

Outros alvos: `make migrate`, `make test`, `make lint`, `make reset`.

---

## Decisões que valem explicação

**O canal WhatsApp é uma réplica de interface, não a API oficial.** Ela fala com o backend pelo mesmo contrato de adaptador que a Cloud API usaria, recebendo payloads em formato de webhook. Trocar em produção é registrar outra implementação — a camada não é um atalho, é a arquitetura correta com implementação trocável.

**O log de auditoria é imutável no banco, não por convenção.** Um trigger recusa `UPDATE` e `DELETE`. Rastreabilidade é requisito não negociável em ambiente judiciário, e disciplina de código não é garantia.

**A decisão de escalar não é tomada por IA.** A política de triagem é uma tabela determinística e auditável. Categoria sensível escala sempre, independentemente da confiança. Onde IA não é necessária, não é usada.

**Sem fonte válida e vigente, o sistema não responde.** Conhecimento vencido escala para humano. Uma resposta desatualizada com carimbo institucional é pior que nenhuma resposta, porque carrega a autoridade da Escola.

**Os dados são 100% fictícios**, conforme a regra do desafio.
