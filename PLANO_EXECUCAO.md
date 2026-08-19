# FAROL v2: Plano de Execução

**Alvo:** demo de hackathon defensável perante banca, cobrindo os 12 itens ESSENCIAIS do §15.
**Alteração de escopo:** sem WhatsApp Business API. O canal WhatsApp é implementado como **Espelho do WhatsApp**: uma réplica fiel de UI (bolhas, ticks, "digitando…", respostas rápidas) que fala com o backend pelo **mesmo contrato de adaptador de canal** que a API oficial usaria. Isso não é um atalho: é o `ChannelAdapter` do §10 com implementação `mirror` no lugar de `whatsapp_cloud_api`. Trocar em produção é trocar uma classe.

---

## Arquitetura resumida

```
apps/
  web/          React + TS + Tailwind  (6 superfícies + console de demo)
  api/          FastAPI                (motor único)
packages/
  contracts/    tipos compartilhados (OpenAPI → TS)
infra/
  docker-compose.yml  (postgres+pgvector)
```

**Contrato de canal** (a peça que absorve a mudança do WhatsApp):

```python
class ChannelAdapter(Protocol):
    channel_id: str                      # "whatsapp" | "ava_widget" | "email" | "phone"
    async def send(self, to: str, msg: OutboundMessage) -> DeliveryReceipt: ...
    async def receive(self, raw: dict) -> InboundMessage: ...   # webhook-shaped
```

- `MirrorWhatsAppAdapter`: entrega via WebSocket para o espelho; `receive()` aceita o **mesmo payload em formato de webhook da Cloud API**, para que a troca futura seja literalmente registrar outro adapter.
- O motor (classificação, RAG, triagem, contratos, gatilhos) **não conhece canal**. Recebe `InboundMessage`, devolve `OutboundMessage`.

---

## FASE 0: Fundação (meio dia)

**Objetivo:** repositório roda com um comando.

- [ ] Scaffold monorepo (`api` FastAPI, `web` Vite+React+TS+Tailwind).
- [ ] `docker-compose` com Postgres 16 + extensão `pgvector`.
- [ ] Migrations (Alembic) com as 12 entidades do §11.
- [ ] Config por env: `LLM_PROVIDER`, `ANTHROPIC_API_KEY`, `CHANNEL_ADAPTER=mirror`.
- [ ] Camada `LLMProvider` abstrata + implementação Anthropic + **fallback determinístico por palavras-chave** (§10, obrigatório: é argumento de defesa).
- [ ] Design tokens: azul-marinho, dourado, neutro claro; verde isolado no espelho do WhatsApp.

**Pronto quando:** `docker compose up` + `make dev` sobe API e web; `/health` responde.

---

## FASE 1: Dados e conhecimento (1 dia)

**Objetivo:** o mundo fictício existe e é consultável.

- [ ] Seed: 3 cursos (com módulos, webconferências, prazos) + **60 participantes** em estados variados: deliberadamente distribuídos para acionar cada um dos 5 gatilhos e cada nível de identidade.
- [ ] Seed: ~15 documentos de orientação pública da EMERON, cada um com **dono e validade** (F31 já nasce no schema).
- [ ] Ingestão: chunking + embeddings → `chunk.vetor` (pgvector, índice HNSW).
- [ ] Busca semântica com filtro de vigência: **documento vencido não entra no retrieval** (F31).
- [ ] Grafo da jornada seedado com as 10 arestas do §4.1 e taxas de travamento iniciais.

**Pronto quando:** `POST /search` devolve trechos relevantes com score e um vencido é comprovadamente excluído.

**Marco de risco:** aqui já se sabe se o RAG tem qualidade. Se os 15 documentos não sustentarem as respostas, o problema é conteúdo, não código: corrigir agora, não na véspera.

---

## FASE 2: Andar 2, o motor RESOLVER (2 dias)

O coração. Tudo depois depende disto.

- [ ] **Identidade progressiva** (F07): resolução por contato → `anonimo | reconhecido | verificado`; código por e-mail simulado. Guard central: campo pessoal só serializa no nível exigido.
- [ ] **Classificação** em 12 categorias (F08), LLM com fallback por palavras-chave.
- [ ] **Pipeline**: retrieval (F09) → enriquecimento com estado individual da matrícula (F10) → geração ancorada com instrução de `NÃO_SEI` → **verificação de ancoragem** (F11), que bloqueia afirmação não sustentada.
- [ ] **Política de triagem determinística** (F12/F13/F14): código puro, tabela do §5.3, zero LLM na decisão. Categoria sensível escala sempre.
- [ ] **Score de confiança** explícito e exposto na resposta.
- [ ] **Dossiê automático** (F17) + **rascunho editável** (F18).
- [ ] **Log de auditoria imutável** (F34) gravado em cada etapa: append-only, sem UPDATE/DELETE concedido à role da app.

**Pronto quando:** teste automatizado prova três casos: responde ancorado, recusa sem fonte, escala categoria sensível mesmo com confiança alta.

---

## FASE 3: Espelho do WhatsApp e widget do AVA (1,5 dia)

**Objetivo:** a conversa acontece de verdade.

- [ ] `MirrorWhatsAppAdapter` + WebSocket bidirecional; payloads em formato webhook Cloud API.
- [ ] **Espelho do WhatsApp** (mobile): moldura de celular, bolhas, timestamp, ticks de entrega, "digitando…", respostas rápidas como botões. Verde fiel: é a única tela que foge da paleta institucional, por realismo.
- [ ] **Widget do AVA** (desktop): mesmo motor, envia `page_context` para que o FAROL saiba em que página a pessoa está.
- [ ] **Fluxo guiado de 2FA** (F15): máquina de estados de 5 passos, verificação por etapa, caminho alternativo, **escalonamento automático após 2 falhas**.
- [ ] Usabilidade como requisito (§12.2): máx. 3 frases, uma ação por mensagem, fonte visível, saída humana sempre presente, alvos ≥44px, contraste AA.

**Pronto quando:** dá para conversar do celular simulado, receber resposta com fonte citada, e completar o fluxo 2FA: incluindo o caminho de falha.

---

## FASE 4: Fila do servidor e o Contrato de Resolução (1,5 dia)

Aqui nasce o primeiro laço fechado: é o que separa o FAROL de um chatbot.

- [ ] **Fila priorizada por consequência** (F19): score = proximidade de prazo × travamento × sensibilidade. Não é FIFO, e a ordenação é explicada na tela.
- [ ] Dossiê expansível legível em 10s, cronômetro, rascunho editável, envio **sempre** com revisão humana.
- [ ] **Contrato de Resolução** (F16 🔄): job agendado pergunta uma vez "resolveu?"; `sim` → fecha e dá peso à fonte; `não` → **não repete a resposta**, escala com a flag *"a orientação padrão falhou neste caso"*; sem retorno → fila de baixa prioridade.
- [ ] **Aprovar como conhecimento oficial** (F20 🔄): resposta do servidor vira documento com dono e validade, indexado na hora.
- [ ] **Deduplicação entre canais** (F21): mesma pessoa + mesma categoria em janela curta = um caso.

**Pronto quando:** um "não resolveu" na demo gera visivelmente um caso escalado com o aviso de falha da orientação padrão.

---

## FASE 5: Andar 1, ANTECIPAR (1 dia)

- [ ] Scheduler (APScheduler) + **regras declarativas em YAML** (§10): editáveis sem código, exibidas na tela de transparência.
- [ ] **5 gatilhos base** (F02) conforme §4.2.
- [ ] **Orçamento de atenção** (F03): saldo por participante/curso; valor esperado = P(evitar atendimento) × custo; gasta só no topo. Ajusta pelo comportamento.
- [ ] **Opt-out em toda mensagem** (F04).
- [ ] **Verificação de efeito** (F05 🔄): cada envio grava a hipótese *"não abrirá atendimento sobre X em 7 dias"*; job confere e registra.
- [ ] **Desativação automática de gatilho inefetivo** (F06 🔄) abaixo do limiar.

**Pronto quando:** avançar o relógio no console de demo dispara gatilho, e avançar mais 7 dias marca a hipótese como confirmada ou refutada.

---

## FASE 6: Andar 3, EXTINGUIR (1,5 dia)

O andar que ganha o hackathon. Não cortar.

- [ ] **Agrupamento semântico** (F24): embeddings dos casos + HDBSCAN; rótulo do cluster gerado por LLM.
- [ ] **Localização da aresta de origem** (F25) cruzando cluster × grafo da jornada.
- [ ] **Ordem de correção** (F26 🔄) no formato exato do §6.2: hipótese, evidência, ação, **previsão numérica**, data de medição, resultado, situação. **Uma por vez.**
- [ ] **Descarte de hipótese falha** (F27 🔄): não bateu a previsão → descarta e propõe a próxima causa.
- [ ] **Auditoria de jornada / partida a frio** (F28): varre o conteúdo seedado procurando os 5 defeitos do §6.3 e emite as primeiras ordens **antes do primeiro atendimento**.
- [ ] **Radar de Causas** (gestor): tela de *recomendação*, não de gráfico, uma ordem em destaque, gráficos secundários abaixo.

**Pronto quando:** a demo mostra a ordem "link da webconferência abaixo da dobra" com previsão de queda e status.

---

## FASE 7: Governança e painéis (1 dia)

- [ ] **Modo Ensaio** (F30): flag global + por categoria. Gera resposta, **não envia**, servidor aprova/corrige; libera categoria ao atingir taxa de acerto. Alternável ao vivo na demo.
- [ ] **Painel de Indicadores** (F35): poucos números, grandes, **métrica invertida no topo**, "atendimentos evitados" acima de "conversas atendidas".
- [ ] **Tela "Como o FAROL decide"** (F32): tabela de triagem, regras YAML do grafo, contador de respostas sem fonte (meta: zero).
- [ ] Curadoria do conhecimento (F31 🔄) completa: expiração por fim de curso, sinalização aos 90 dias sem citação, rebaixamento automático por taxa de "não resolveu".

---

## FASE 8: Console de demonstração e ensaio (1 dia)

Trata a apresentação como feature, porque é onde o produto é julgado.

- [ ] Console: trocar participante, **avançar o tempo**, disparar gatilho manualmente, alternar Modo Ensaio, **resetar tudo** ao estado inicial.
- [ ] Roteiro de 6 minutos ensaiado ponta a ponta:
  1. Gatilho proativo chega **antes** da pergunta.
  2. Pergunta pessoal: resposta sobre *o caso dela*, com fonte.
  3. Pergunta sem fonte: **recusa** institucional e escalonamento com dossiê.
  4. Fila do servidor: dossiê lido em 10s, rascunho, aprovar como conhecimento.
  5. Contrato de Resolução: "não resolveu" → escala com o aviso.
  6. Radar de Causas: ordem de correção com previsão numérica.
- [ ] Seed determinístico e reset idempotente: **a demo nunca pode falhar por estado sujo**.
- [ ] Passagem de acessibilidade (contraste AA, teclado, ARIA) e responsividade.

---

## Cronograma

| Fase | Esforço | Acumulado |
|---|---|---|
| 0 Fundação | 0,5 d | 0,5 |
| 1 Dados e conhecimento | 1,0 d | 1,5 |
| 2 Motor RESOLVER | 2,0 d | 3,5 |
| 3 Espelho WhatsApp + widget | 1,5 d | 5,0 |
| 4 Fila + Contrato de Resolução | 1,5 d | 6,5 |
| 5 ANTECIPAR | 1,0 d | 7,5 |
| 6 EXTINGUIR | 1,5 d | 9,0 |
| 7 Governança e painéis | 1,0 d | 10,0 |
| 8 Console e ensaio | 1,0 d | 11,0 |

**Se o prazo apertar, corte nesta ordem:** widget do AVA → deduplicação entre canais → auditoria de jornada → efeito de rede. **Nunca corte** os 4 laços 🔄 (F05, F16, F20, F26): são a tese do produto. Um FAROL sem laço é o quarto banner.

---

## Cobertura do catálogo

Fases 0: 8 entregam F01, F22, F24, F28, F30, F35 (**33 de 35**).
Fora do escopo da demo, por dependerem de infraestrutura externa inexistente: **F23** (conversão de ligação perdida, precisa de telefonia) e **F29** (efeito de rede entre escolas: precisa de mais de uma escola operando). Ambas ficam como contrato de adaptador declarado e argumento de roadmap, não como código morto.

---

## Notas de decisão

- **Espelho do WhatsApp:** perante a banca, isso se defende, o §15 já lista "API oficial do WhatsApp" em ❌ NÃO CONSTRUIR, e o §18 sustenta que a camada mock é a arquitetura correta com implementação trocável, não um atalho.
- **LLM:** OpenAI `gpt-5-nano` para classificação e geração ancorada, com **structured outputs em modo estrito**: o schema garante que toda resposta traga o campo `fontes`, que é o que a verificação de ancoragem (F11) confere na Fase 2. Os dois papéis são variáveis de ambiente separadas: se a taxa de resposta sem fonte incomodar, a geração sobe de modelo sem tocar em código. Fallback determinístico obrigatório e demonstrável (é resposta a uma pergunta previsível da banca).
- **Embeddings:** `text-embedding-3-small` (1536 dimensões), mesma chave do LLM. Alternativa offline via `EMBEDDING_PROVIDER=local`, mas mudar isso exige regerar a migration do `chunk`.
- **Dados:** 100% fictícios, conforme regra do desafio.
- **Testes:** cobertura concentrada na política de triagem e na verificação de ancoragem. São as duas peças cujo erro é institucionalmente caro.
