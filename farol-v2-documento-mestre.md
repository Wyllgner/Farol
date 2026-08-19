# FAROL v2
## Documento Mestre do Produto

**Fluxo de Atendimento, Resolução e Orientação em Laço**
*Solução para o desafio da Seção de Coordenação de Educação a Distância: EMERON / TJRO*

> **Slogan:** Responde antes da pergunta. E trabalha para nunca mais precisar responder.

---

## SUMÁRIO

1. [O problema e a tese](#1-o-problema-e-a-tese)
2. [O que é o FAROL](#2-o-que-é-o-farol)
3. [Princípio arquitetural: tudo é laço fechado](#3-princípio-arquitetural-tudo-é-laço-fechado)
4. [Andar 1: ANTECIPAR](#4-andar-1--antecipar)
5. [Andar 2: RESOLVER](#5-andar-2--resolver)
6. [Andar 3: EXTINGUIR](#6-andar-3--extinguir)
7. [Camada transversal: Confiança e Governança](#7-camada-transversal--confiança-e-governança)
8. [Catálogo completo de funcionalidades](#8-catálogo-completo-de-funcionalidades)
9. [Fluxo ponta a ponta](#9-fluxo-ponta-a-ponta)
10. [Arquitetura técnica](#10-arquitetura-técnica)
11. [Modelo de dados](#11-modelo-de-dados)
12. [Interfaces e usabilidade](#12-interfaces-e-usabilidade)
13. [Segurança, LGPD e limites éticos](#13-segurança-lgpd-e-limites-éticos)
14. [Métricas e impacto](#14-métricas-e-impacto)
15. [Escopo do MVP](#15-escopo-do-mvp)
16. [Roadmap](#16-roadmap)
17. [Riscos e mitigações](#17-riscos-e-mitigações)
18. [Defesa perante a banca](#18-defesa-perante-a-banca)
19. [Suposições declaradas](#19-suposições-declaradas)

---

# 1. O PROBLEMA E A TESE

## 1.1 O problema declarado

A SECOEAD atende diariamente, por quatro canais (WhatsApp institucional, e-mail, chat do e-mail e telefone), um alto volume de solicitações de baixa complexidade: acesso às plataformas, redefinição de senha, autenticação em dois fatores, localização de cursos, prazos, webconferências e certificados. Cada atendimento é individual, mesmo quando a resposta é padronizada.

O custo real não é o tempo de responder. É a **fragmentação da atenção**: a equipe que deveria acompanhar a execução dos cursos, conferir relatórios e resolver casos complexos passa o dia sendo interrompida.

## 1.2 A tese: o problema por trás do problema

A informação mais importante do desafio está escrita no próprio formulário do setor:

> *"Essas ações facilitaram o acesso às informações e aos procedimentos pelos participantes. **No entanto, não reduziram de forma significativa o volume de atendimentos**, pois muitos usuários continuam procurando o setor pelos canais de atendimento para obter orientação individualizada, **mesmo quando as instruções já estão disponíveis**."*

A EMERON **já** enviou e-mail de boas-vindas com todas as orientações. **Já** destacou o link de redefinição de senha na home do AVA. **Já** publicou banner e vídeo sobre 2FA. E o volume não caiu.

> ### 🎯 TESE CENTRAL
> **O problema não é falta de informação. Se fosse, já estaria resolvido.**
>
> Qualquer solução que apenas reorganize, indexe ou "chatbotize" a mesma informação está resolvendo um problema que já foi resolvido, e vai falhar exatamente como o banner falhou.

## 1.3 As quatro causas reais

**Causa 1: Assimetria de esforço e certeza.**
Perguntar a um humano custa 8 segundos e devolve **certeza**. Buscar sozinho custa 4 minutos e devolve dúvida sobre se aquilo se aplica ao caso da pessoa. Não é preguiça: é escolha racional. Enquanto o autoatendimento for mais caro e menos confiável que mandar "bom dia" no WhatsApp, ele perde.

**Causa 2: As dúvidas parecem genéricas, mas são pessoais e transacionais.**
"Como emito meu certificado?" quase nunca significa "não sei o procedimento". Significa *"eu fiz e não apareceu: o que está errado **comigo**?"*. **Nenhum FAQ responde a uma pergunta cujo objeto é o estado individual do usuário.** É por isso que a pessoa procura um humano: só o humano abre o sistema e olha o caso dela.

**Causa 3: Todo o suporte atual é *pull* e fora de tempo.**
O e-mail chega no dia 1. A dúvida nasce no dia 23, às 22h47, quando o 2FA rejeita o código. A informação certa existe, mas está no lugar errado, na hora errada e no canal errado.

**Causa 4: Cada atendimento é conhecimento que evapora.**
Quatro canais, nenhum registro estruturado. Cada pergunta repetida é o **sintoma de um defeito a montante**: uma página confusa, um prazo mal redigido, um botão escondido. Responder para sempre é enxugar gelo com excelência.

## 1.4 A pergunta que orienta o produto

> Paramos de perguntar **"como responder melhor?"**
> e passamos a perguntar: **"como fazer a pergunta deixar de existir?"**

---

# 2. O QUE É O FAROL

O FAROL é uma **camada de atendimento inteligente de três andares**, entregue nos canais que já existem, cuja meta declarada é ser usada cada vez menos.

| Andar | Verbo | O que faz | Por que nenhum chatbot faz |
|---|---|---|---|
| **1** | 🔭 **ANTECIPAR** | Detecta onde o participante travou e entrega a orientação certa **antes da pergunta existir** | Chatbot espera ser acionado |
| **2** | 💬 **RESOLVER** | Responde sobre **o caso individual** da pessoa, ancorado em fonte oficial; recusa quando não sabe e escala com dossiê pronto | Chatbot responde igual para todos e responde tudo |
| **3** | 📉 **EXTINGUIR** | Descobre onde na jornada a dúvida nasce e emite ordens de correção da plataforma | Chatbot absorve demanda; não elimina causa |

O nome não é decorativo: **um farol não espera o navio pedir socorro, ele avisa antes da rocha.** E o "em Laço" descreve a propriedade arquitetural central, explicada a seguir.

---

# 3. PRINCÍPIO ARQUITETURAL: TUDO É LAÇO FECHADO

Esta é a decisão de engenharia que sustenta a coerência do produto com a própria tese.

Se o banner falhou porque ninguém mediu seu efeito, um sistema que age sem verificar consequência é apenas **um banner mais sofisticado**. Por isso, **cada andar do FAROL fecha o próprio laço**:

```
ANTECIPAR  →  agiu  →  verifica se o atendimento foi evitado  →  ajusta o gatilho
RESOLVER   →  respondeu  →  verifica se resolveu de fato  →  ajusta o conhecimento
EXTINGUIR  →  corrigiu  →  verifica se o volume caiu  →  ajusta a hipótese
```

**Nenhuma ação do FAROL termina no envio. Toda ação termina na verificação do efeito.**

Consequência prática: o sistema melhora sozinho com o uso, e nenhuma afirmação de impacto depende de fé, todas são medidas.

---

# 4. ANDAR 1: ANTECIPAR

**Objetivo:** eliminar a pergunta antes que ela seja formulada.

## 4.1 Grafo da Jornada

O motor não opera sobre regras escritas à mão, e sim sobre um **grafo da jornada do participante**:

```
Inscrição → Primeiro acesso → Configuração 2FA → Localização do curso →
Consumo de conteúdo → Webconferência → Atividades → Prazo → Conclusão → Certificado
```

Cada **aresta** carrega uma taxa de travamento observada. Quando uma aresta apresenta travamento acima da média, o FAROL age ali, inclusive em pontos que ninguém programou.

**Por que isso importa:** gatilhos hardcoded exigem um programador para cada dúvida nova. O grafo **descobre** onde as pessoas param. E é a mesma estrutura de dados usada pelo Andar 3: os dois andares operam sobre o mesmo modelo, o que elimina duplicação conceitual.

O grafo é **editável por servidor**, sem código.

## 4.2 Gatilhos base

Cinco gatilhos partem configurados, derivados das arestas de maior travamento conhecido:

| # | Condição | Ação |
|---|---|---|
| 1 | Inscrito há +2 dias e nunca acessou | Link de primeiro acesso com passo a passo |
| 2 | Acessou mas não configurou 2FA | Oferta de configuração guiada |
| 3 | Faltam 3 dias para o prazo e progresso < 70% | Aviso com a atividade pendente e link direto |
| 4 | Webconferência em 1 hora | Link e instrução de entrada |
| 5 | Certificado liberado e não retirado há +2 dias | Link direto de emissão |

## 4.3 Orçamento de Atenção

Mensagem não solicitada de um Tribunal é uma faca de dois gumes. O FAROL não usa uma regra ingênua de frequência: usa um **orçamento de atenção por participante**.

- Cada pessoa tem saldo limitado de interrupções por curso.
- Cada mensagem candidata tem um **valor esperado** = probabilidade de evitar um atendimento × custo desse atendimento.
- O FAROL gasta o orçamento apenas nas mensagens de maior valor esperado.
- O orçamento se ajusta ao comportamento: quem ignora sistematicamente recebe menos; quem interage recebe mais.
- Toda mensagem proativa traz opção de desativar avisos.

## 4.4 Verificação de Efeito 🔄

**O laço do Andar 1.** Toda mensagem proativa gera uma **hipótese verificável**:

> *"Esta pessoa não abrirá atendimento sobre este assunto nos próximos 7 dias."*

O sistema verifica e registra o resultado. Isso produz a métrica que realmente importa: **taxa de antecipação efetiva**: não quantas mensagens foram enviadas, mas quantos atendimentos deixaram de existir por causa delas.

Gatilhos com efetividade abaixo do limiar são **automaticamente desativados**. O sistema não insiste no que não funciona, que foi exatamente o erro do banner.

---

# 5. ANDAR 2: RESOLVER

**Objetivo:** resolver de verdade, no canal da pessoa, sem nunca inventar, e preservar o humano para o que é humano.

## 5.1 Identidade Progressiva

Três níveis de acesso, escalando conforme a confiança na identidade. Um dado pessoal **nunca** sai no nível anônimo.

| Nível | Como se atinge | O que o FAROL pode revelar |
|---|---|---|
| **Anônimo** | Qualquer contato | Apenas informação pública: como acessar, onde fica o curso, prazos gerais, procedimentos |
| **Reconhecido** | Contato bate com o cadastro | Estado do curso, progresso, prazo pessoal, situação do certificado |
| **Verificado** | Código enviado ao e-mail institucional | Dados sensíveis e ações que afetam o cadastro |

O produto continua útil no nível anônimo: o que cobre o **público externo não cadastrado**, ignorado na maioria das soluções.

## 5.2 Pipeline de resolução

**1. Classificação de intenção** em 12 categorias: acesso · senha · 2FA · localização de curso · prazo · webconferência · certificado · inscrição · conteúdo · reclamação · sensível · outros.

**2. Recuperação semântica** dos trechos relevantes da base de conhecimento oficial.

**3. Enriquecimento com estado individual**: último acesso, progresso, 2FA, prazo, situação do certificado, histórico de atendimentos.

**4. Geração ancorada**, sob restrição rígida: *responder exclusivamente com base nos trechos recuperados e nos dados de estado; se insuficiente, retornar NÃO_SEI*.

**5. Verificação de ancoragem**: se a resposta contiver afirmação não sustentada pelas fontes, ela é bloqueada.

## 5.3 Política de Triagem

Explícita, determinística e auditável: **não é IA que decide quando escalar**:

| Situação | Ação |
|---|---|
| Confiança alta + assunto não sensível | Responde direto |
| Confiança média | Responde e oferece falar com humano |
| Confiança baixa ou NÃO_SEI | **Recusa e escala com dossiê** |
| Categoria sensível (dado pessoal, exceção de prazo, saúde, financeiro, reclamação, urgência) | **Escala sempre**, independentemente da confiança |

A recusa é institucional e digna:

> *"Essa situação exige análise de um servidor da SECOEAD e eu não posso decidir por eles. Já encaminhei seu caso com todo o contexto e você receberá retorno por este mesmo canal."*

## 5.4 Fluxos Guiados Executáveis

Para procedimentos que já falharam como texto (2FA é o caso emblemático: já existe banner e vídeo), o FAROL **acompanha** em vez de orientar:

- Passo a passo com verificação a cada etapa: *"Conseguiu ver a tela com o QR Code? Sim / Não / Estou vendo outra coisa"*
- Progresso visual (passo 2 de 5)
- Caminho alternativo quando o participante responde que não conseguiu
- **Escalonamento automático após duas falhas consecutivas**

> **Princípio:** orientar não é o mesmo que acompanhar. Foi por isso que o vídeo não funcionou.

**Limite ético e de segurança:** o FAROL **nunca executa operação de credencial**. Não redefine senha, não altera cadastro, não emite certificado. Ele aciona o fluxo oficial da plataforma e acompanha a pessoa até o fim.

## 5.5 Contrato de Resolução 🔄

**O laço do Andar 2, e a funcionalidade que mais claramente separa o FAROL de um chatbot.**

Cada atendimento é um contrato aberto que só fecha com confirmação:

1. O FAROL responde.
2. Se a pessoa não retornou, ele pergunta **uma vez**, no momento adequado: *"Conseguiu emitir o certificado?"*
3. **"Sim"** → caso encerrado; a resposta é validada e ganha peso na base de conhecimento.
4. **"Não"** → o FAROL **não repete a resposta**. Escala imediatamente, e o dossiê inclui a informação mais valiosa que existe: *"a orientação padrão não funcionou neste caso"*.
5. **Sem retorno** → o caso permanece aberto em fila de baixa prioridade.

**O que isso resolve:** captura o **erro silencioso**, o caso perigoso em que o sistema tem confiança alta, responde errado, e ninguém percebe. E reproduz digitalmente o que o bom atendente humano faz e o chatbot nunca faz: verificar se resolveu.

## 5.6 Escalonamento com Dossiê

Quando escala, o servidor não recebe "oi, preciso de ajuda". Recebe o caso montado:

- Identificação do participante e curso
- Estado atual completo (último acesso, progresso, 2FA, prazo, certificado)
- Categoria, nível de sensibilidade e urgência
- Resumo do que já foi tentado, incluindo se a orientação padrão falhou
- Transcrição consolidada da conversa, **unificada entre canais**
- **Rascunho de resposta sugerido e editável**

**Nada é enviado automaticamente em nome da instituição.** O servidor sempre revisa.

## 5.7 Fila priorizada por consequência

A fila não é ordenada por ordem de chegada nem por urgência genérica, e sim pela **consequência de não atender**:

Prazo vence em 2 dias e a pessoa está travada → topo.
Dúvida sobre certificado de curso concluído há 3 meses → base.

Isso alinha a fila ao que a instituição efetivamente perde.

## 5.8 Aprovação como conhecimento

Ao responder um caso escalado, o servidor pode acionar **"Aprovar como conhecimento oficial"**. A resposta entra na base, passa a ser citável como fonte, e casos semelhantes deixam de escalar.

**A base cresce pela operação normal, com curadoria humana.** A cada escalonamento, o sistema fica melhor, e a curva de escalonamento cai sozinha.

## 5.9 Cobertura dos quatro canais

O desafio pede explicitamente que a solução não se limite a um canal:

| Canal | Abordagem |
|---|---|
| **WhatsApp institucional** | Canal principal: onde o público já está, sem exigir mudança de hábito |
| **Widget no AVA** | Mesmo motor, com contexto de plataforma (sabe em que página o usuário está) |
| **E-mail** | O FAROL lê a caixa institucional, classifica, responde ou escala |
| **Telefone** | **Sem construir URA.** Ligação não atendida ou fora do expediente dispara mensagem automática: *"Vi que você ligou para a Escola. Posso ajudar por aqui?"*, convertendo o canal mais caro no mais barato |

**Deduplicação entre canais:** mesma pessoa + mesma demanda em dois canais = **um único caso**. Ataca diretamente o retrabalho citado no formulário.

---

# 6. ANDAR 3: EXTINGUIR

**Objetivo:** fazer a pergunta deixar de existir. É o andar que nenhuma outra solução terá.

## 6.1 Descoberta de causa-raiz

O FAROL agrupa as demandas por similaridade semântica, cruza com o grafo da jornada e localiza **a aresta onde a dúvida nasce**, não a categoria genérica, mas o ponto exato de falha.

Exemplo: o assunto mais frequente não é "senha". É *"não encontro a webconferência"*, e 71% vem de um único curso.

## 6.2 Ordem de Correção com hipótese, previsão e medição 🔄

**O laço do Andar 3.** Não é uma sugestão em um painel: é um **experimento com método**:

```
HIPÓTESE:  o link da webconferência está abaixo da dobra no módulo 2,
           e por isso as pessoas não o encontram.

EVIDÊNCIA: 71% das dúvidas de webconferência vêm deste curso;
           taxa de travamento nesta aresta é 3,2x a média.

AÇÃO:      mover o link para o topo do módulo.

PREVISÃO:  queda de 31 atendimentos/mês nesta categoria.

MEDIÇÃO:   30 dias após a implementação.

RESULTADO: [preenchido automaticamente pelo sistema]

SE FALHAR: hipótese descartada; o FAROL propõe a próxima causa provável.
```

**Uma ordem por vez, priorizada por impacto estimado**, para caber na rotina de quem já está sobrecarregado. Status: Pendente / Em andamento / Implementada.

> O FAROL não dá palpite. Faz uma previsão numérica e volta em 30 dias para dizer se acertou.

## 6.3 Auditoria da Jornada (partida a frio)

O Andar 3 depende de histórico acumulado: no dia 1 a base está vazia. Para gerar valor imediatamente, o FAROL executa uma **auditoria automática do conteúdo da plataforma**, procurando defeitos conhecidos que geram dúvida:

- informação de prazo ausente ou ambígua
- link crítico posicionado abaixo da dobra
- instrução escrita em linguagem de sistema, não de pessoa
- página sem caminho visível para suporte
- texto que pressupõe conhecimento não fornecido

Isso produz as primeiras ordens de correção **antes do primeiro atendimento**.

## 6.4 Efeito de rede entre escolas

O catálogo de causas-raiz é transferível. Um padrão de travamento descoberto em uma escola judicial vira **conhecimento anônimo e agregado** para todas as escolas conectadas: nenhum dado pessoal circula, apenas padrões de defeito de plataforma.

**Cada escola nova torna todas as outras melhores.** É a única característica genuinamente impossível de copiar, porque não é código: é acúmulo.

---

# 7. CAMADA TRANSVERSAL: CONFIANÇA E GOVERNANÇA

## 7.1 Modo Ensaio

**A funcionalidade que torna a adoção institucionalmente possível.**

Nas primeiras semanas, o FAROL roda em modo sombra: **gera a resposta, mas não envia**. O servidor vê o que ele teria respondido, aprova ou corrige. Só depois de atingir uma taxa de acerto acordada, uma categoria é liberada para resposta automática: **categoria por categoria**.

> Nenhuma instituição do Judiciário liga no dia 1 um sistema que fala em nome da Casa.
> **Não pedimos confiança. Pedimos duas semanas de observação.**

## 7.2 Envelhecimento e curadoria do conhecimento

Uma resposta desatualizada com carimbo institucional é **pior** que nenhuma resposta, porque carrega a autoridade da Escola. Por isso todo documento da base tem validade e dono:

- Conteúdo com data (prazos, calendário) **expira automaticamente** ao fim do curso.
- Documento não citado em 90 dias é sinalizado para revisão.
- Documento que gera taxa de "não resolveu" acima do limiar (via Contrato de Resolução) é **rebaixado automaticamente**.
- **Sem fonte válida e vigente, o FAROL escala.** Conhecimento vencido não responde.

## 7.3 Transparência de decisão

Existe uma tela pública **"Como o FAROL decide"**, mostrando a política de triagem em tabela, as regras do grafo e o contador de respostas sem fonte (meta: zero). O sistema não é caixa-preta nem para o servidor nem para o gestor.

## 7.4 Espelho do Servidor

O mesmo motor, com base de conhecimento diferente, atendendo **docentes, palestrantes e a própria equipe**: *"como lanço a nota", "como abro a sala da webconferência", "onde vejo a lista de inscritos"*.

Custo marginal quase zero: é a mesma máquina com outro conteúdo. E prova na prática a tese de escalabilidade: trocar a base adapta o FAROL para outro público.

## 7.5 Auditoria

Toda interação é registrada em log imutável: entrada, classificação, fontes recuperadas, confiança calculada, decisão de triagem, resposta gerada, ação do servidor. Rastreabilidade completa: requisito não negociável em ambiente judiciário.

---

# 8. CATÁLOGO COMPLETO DE FUNCIONALIDADES

| # | Funcionalidade | Andar | Fecha laço |
|---|---|---|---|
| F01 | Grafo da jornada com detecção de travamento | 1 | |
| F02 | Cinco gatilhos proativos base | 1 | |
| F03 | Orçamento de atenção por participante | 1 | |
| F04 | Opt-out de avisos em toda mensagem | 1 | |
| F05 | **Verificação de efeito da antecipação** | 1 | 🔄 |
| F06 | Desativação automática de gatilho inefetivo | 1 | 🔄 |
| F07 | Identidade progressiva em três níveis | 2 | |
| F08 | Classificação de intenção em 12 categorias | 2 | |
| F09 | Recuperação semântica na base oficial | 2 | |
| F10 | Resposta personalizada por estado individual | 2 | |
| F11 | Verificação de ancoragem em fonte | 2 | |
| F12 | Política de triagem determinística | 2 | |
| F13 | Recusa institucional com escalonamento | 2 | |
| F14 | Escalonamento incondicional de categoria sensível | 2 | |
| F15 | Fluxo guiado executável com verificação por etapa | 2 | |
| F16 | **Contrato de resolução com confirmação** | 2 | 🔄 |
| F17 | Dossiê automático para o servidor | 2 | |
| F18 | Rascunho de resposta editável | 2 | |
| F19 | Fila priorizada por consequência | 2 | |
| F20 | Aprovação de resposta como conhecimento oficial | 2 | 🔄 |
| F21 | Deduplicação de demanda entre canais | 2 | |
| F22 | Cobertura WhatsApp + widget AVA + e-mail | 2 | |
| F23 | Conversão de ligação perdida em mensagem | 2 | |
| F24 | Agrupamento semântico de demandas | 3 | |
| F25 | Localização da aresta de origem da dúvida | 3 | |
| F26 | **Ordem de correção com previsão e medição** | 3 | 🔄 |
| F27 | Descarte de hipótese que falhou | 3 | 🔄 |
| F28 | Auditoria da jornada para partida a frio | 3 | |
| F29 | Catálogo de causas transferível entre escolas | 3 | |
| F30 | Modo Ensaio com liberação por categoria | T | |
| F31 | Validade e curadoria do conhecimento | T | 🔄 |
| F32 | Tela "Como o FAROL decide" | T | |
| F33 | Espelho do Servidor (docentes e equipe) | T | |
| F34 | Log de auditoria imutável | T | |
| F35 | Painel de indicadores com métrica invertida | T | |

**🔄 = funcionalidade que fecha um laço de aprendizado.** São 9 das 35, e são elas que fazem o sistema melhorar sozinho.

---

# 9. FLUXO PONTA A PONTA

```
┌─ ENTRADA ─────────────────────────────────────────────────┐
│                                                            │
│  PROATIVA                        REATIVA                   │
│  Grafo detecta travamento        Mensagem em linguagem     │
│  na aresta X                     natural (4 canais)        │
│         │                               │                  │
│         ▼                               ▼                  │
│  Orçamento de atenção          Identidade progressiva      │
│  autoriza o envio?             (anônimo/reconhecido/       │
│         │                       verificado)                │
└─────────┼───────────────────────────────┼──────────────────┘
          │                               │
          │                               ▼
          │                    ┌─ PROCESSAMENTO ─────────┐
          │                    │ Deduplicação entre      │
          │                    │ canais                  │
          │                    │ Classificação de        │
          │                    │ intenção (12 cat.)      │
          │                    └───────────┬─────────────┘
          │                                ▼
          │                    ┌─ INTELIGÊNCIA ──────────┐
          │                    │ Recuperação semântica   │
          │                    │ + estado individual     │
          │                    │ + geração ancorada      │
          │                    │ + verificação de fonte  │
          │                    │ + cálculo de confiança  │
          │                    └───────────┬─────────────┘
          │                                ▼
          │                    ┌─ DECISÃO ───────────────┐
          │                    │ Política de triagem     │
          │                    │ determinística          │
          │                    └──┬──────────────────┬───┘
          │                       │                  │
          ▼                       ▼                  ▼
   ┌─ AÇÃO ────────┐   ┌─ RESOLVE ─────┐   ┌─ ESCALA ────────┐
   │ Mensagem      │   │ Resposta curta│   │ Dossiê completo │
   │ proativa      │   │ + fonte       │   │ + rascunho      │
   │ personalizada │   │ Fluxo guiado  │   │ Fila por        │
   │               │   │ executável    │   │ consequência    │
   └───────┬───────┘   └───────┬───────┘   └────────┬────────┘
           │                   │                    │
           ▼                   ▼                    ▼
   ┌─ LAÇO 1 ──────┐   ┌─ LAÇO 2 ──────┐   ┌─ APRENDIZADO ───┐
   │ Evitou o      │   │ Contrato de   │   │ Servidor aprova │
   │ atendimento?  │   │ resolução:    │   │ como            │
   │ Se não,       │   │ "resolveu?"   │   │ conhecimento    │
   │ desativa      │   │ Se não,escala │   │ oficial         │
   │ o gatilho     │   │ com o aviso   │   │                 │
   └───────┬───────┘   └───────┬───────┘   └────────┬────────┘
           │                   │                    │
           └───────────────────┴────────────────────┘
                               ▼
                  ┌─ ANDAR 3: EXTINGUIR ─────────┐
                  │ Agrupa demandas              │
                  │ Localiza aresta de origem    │
                  │ Emite ordem de correção      │
                  │ com previsão numérica        │
                  └──────────────┬───────────────┘
                                 ▼
                  ┌─ LAÇO 3 ─────────────────────┐
                  │ Mediu em 30 dias:            │
                  │ o volume caiu?               │
                  │ Sim → causa extinta          │
                  │ Não → descarta hipótese,     │
                  │       propõe a próxima       │
                  └──────────────┬───────────────┘
                                 ▼
                    MENOS CAUSAS → MENOS DÚVIDAS
                       → MENOS ATENDIMENTOS
```

---

# 10. ARQUITETURA TÉCNICA

| Camada | Escolha | Justificativa |
|---|---|---|
| **Frontend** | React + TypeScript + Tailwind | Uma base de código, três superfícies (WhatsApp, widget AVA, painéis) |
| **Backend** | FastAPI (Python) | Ecossistema de IA maduro; velocidade de desenvolvimento |
| **Banco** | PostgreSQL + pgvector | Um único banco para dados relacionais e busca semântica: menos peças, menos falhas |
| **Conhecimento** | RAG com chunking sobre conteúdo **público** | Respostas ancoradas e auditáveis; trocar conteúdo não exige retreinar nada |
| **LLM** | API de modelo de linguagem | Classificação, geração ancorada, sumarização de dossiê, rotulagem de agrupamentos |
| **Grafo da jornada** | Modelo de estados + métricas por aresta | Estrutura compartilhada entre Andar 1 e Andar 3 |
| **Motor de eventos** | Scheduler + regras declarativas em YAML | Auditável e editável por servidor, não é caixa-preta |
| **Causa-raiz** | Embeddings + clusterização (HDBSCAN) | Descobre padrões que ninguém categorizou previamente |
| **Integração** | **Adaptadores com contrato de API definido** | No protótipo, mock; em produção, troca a implementação sem mudar o contrato |
| **Canais** | Adaptador por canal sobre um motor único | Adicionar canal não duplica lógica |
| **Segurança** | Identidade progressiva · minimização de dados · log imutável · segregação base pública × dados pessoais | LGPD e sigilo em ambiente judiciário |

**Tecnologia deliberadamente ausente:** visão computacional, blockchain, IoT, geoprocessamento, fine-tuning de modelo. Nenhuma delas resolve este problema. Dizer isso é sinal de maturidade, não de limitação.

**Fallback obrigatório:** se a chamada ao modelo falhar, classificação determinística por palavras-chave assume. O sistema degrada com elegância; nunca quebra.

---

# 11. MODELO DE DADOS

**Entidades principais:**

| Entidade | Campos-chave |
|---|---|
| `participante` | identificação, perfil (magistrado/servidor/estudante/docente/externo), canal preferido, nível de identidade, saldo de atenção |
| `curso` | título, datas, módulos, webconferências, prazo |
| `matricula` | participante, curso, data de inscrição, último acesso, progresso, 2FA configurado, prazo, situação do certificado, **aresta atual no grafo** |
| `documento_conhecimento` | título, conteúdo, dono, **validade**, taxa de resolução efetiva, situação |
| `chunk` | documento, texto, vetor |
| `conversa` / `mensagem` | canal, participante, conteúdo, timestamp, direção |
| `caso` | categoria, sensibilidade, confiança, canal, situação, dossiê, **contrato de resolução (aberto/confirmado/falhou)** |
| `evento_proativo` | gatilho, participante, envio, **hipótese, verificação, efeito medido** |
| `aresta_jornada` | origem, destino, taxa de travamento, volume |
| `agrupamento_causa` | rótulo, volume, aresta de origem, cursos afetados |
| `ordem_correcao` | hipótese, evidência, ação, **previsão numérica, data de medição, resultado, situação** |
| `log_auditoria` | interação completa, imutável |

---

# 12. INTERFACES E USABILIDADE

## 12.1 As seis superfícies

1. **Simulador de WhatsApp** (participante, celular): réplica fiel: bolhas, horário, "digitando…", respostas rápidas.
2. **Widget no AVA** (participante, desktop): bolha de ajuda com contexto de página.
3. **Fila do Servidor** (desktop): casos priorizados, dossiê expansível, rascunho editável, cronômetro, botão de aprovação de conhecimento.
4. **Radar de Causas** (gestor): **tela de recomendação, não de gráfico**: uma ordem de correção em destaque com previsão e status; gráficos secundários abaixo.
5. **Indicadores**: poucos números, grandes, com a métrica invertida no topo.
6. **Como o FAROL decide**: política de triagem, regras do grafo, contador de respostas sem fonte.

*(+ Console de Demonstração para apresentação: trocar participante, avançar o tempo, disparar gatilhos, resetar.)*

## 12.2 Doze princípios de usabilidade

O público inclui magistrados, servidores, docentes e público externo, com níveis muito diferentes de familiaridade digital. Estes são **requisitos**, não recomendações:

1. **Zero curva de aprendizado**: o participante usa o WhatsApp que já usa. Sem cadastro, sem tutorial, sem app novo.
2. **Uma ação por mensagem**: no máximo uma ação principal e um botão de escape. Nunca um menu de oito opções.
3. **Resposta curta primeiro**: máximo 3 frases, com opção "quero o passo a passo completo". Nada de paredes de texto.
4. **Linguagem de pessoa, não de sistema**: *"Seu certificado ainda não saiu porque falta 1 atividade"*, nunca *"Status: pendência de conclusão"*.
5. **Saída humana sempre visível**: a um toque, em qualquer ponto. Ninguém fica preso num robô.
6. **Transparência de fonte**: toda resposta mostra de onde veio.
7. **Nunca fingir certeza**, se não sabe, diz e escala.
8. **Acessibilidade**: contraste AA, fonte ≥16px no chat, alvos de toque ≥44px, navegação por teclado, rótulos ARIA, sem depender apenas de cor.
9. **Responsivo de verdade**: celular para o participante, desktop para servidor e gestor.
10. **Velocidade para o servidor**: o dossiê deve ser lido em 10 segundos: hierarquia forte, crítico no topo, rascunho pronto.
11. **Feedback imediato**: indicador de digitação, confirmação de envio, estados de carregamento, nenhuma tela em branco.
12. **Reversibilidade**: o servidor edita qualquer sugestão antes de enviar. Nada sai automaticamente em nome da instituição.

## 12.3 Identidade visual

Sóbria e institucional, adequada ao Judiciário, mas moderna: azul-marinho profundo, dourado discreto como destaque, fundo claro e neutro, verde reservado ao simulador de WhatsApp por fidelidade. Tipografia sem serifa de alta legibilidade, cantos suaves, sombras discretas, muito espaço em branco. Sem gradientes chamativos e sem estética de startup genérica.

---

# 13. SEGURANÇA, LGPD E LIMITES ÉTICOS

O formulário confirma: *"Há dados pessoais ou informações sigilosas? Sim."*

**Controles implementados:**

| Controle | Descrição |
|---|---|
| Identidade progressiva | Dado pessoal exige nível Reconhecido; dado sensível exige Verificado |
| Minimização | Só o dado necessário para aquela resposta; nunca CPF ou e-mail completos |
| Segregação | Base de conhecimento pública separada fisicamente de dados pessoais |
| Não execução de credencial | O FAROL nunca redefine senha nem altera cadastro: apenas aciona o fluxo oficial |
| Escalonamento incondicional | Categorias sensíveis vão para humano sempre |
| Log imutável | Toda interação auditável ponta a ponta |
| Conhecimento com validade | Fonte vencida não responde |
| Modo Ensaio | Nenhuma resposta automática antes de acerto comprovado por categoria |
| Dados no hackathon | 100% fictícios, conforme regra do desafio |

---

# 14. MÉTRICAS E IMPACTO

## 14.1 A métrica invertida

> **Sucesso, aqui, é este painel diminuir.**

Todo painel de chatbot comemora quando o número de conversas sobe. O do FAROL comemora quando desce, porque significa que as causas estão sendo eliminadas. É a única solução cujo KPI é a própria irrelevância futura.

## 14.2 Métricas primárias

| Métrica | Definição | Meta 6 meses |
|---|---|---|
| Taxa de resolução sem humano | Casos encerrados sem servidor | ≥ 60% |
| **Antecipação efetiva** | Atendimentos comprovadamente evitados por mensagem proativa | ≥ 35% dos casos previsíveis |
| **Taxa de confirmação de resolução** | Casos com "sim, resolveu" | ≥ 80% |
| Horas devolvidas à equipe | Atendimentos evitados × tempo médio | ≥ 25h/mês |
| Tempo até resolução | Entrada → encerramento | < 1 min (casos simples) |
| Tempo de tratamento humano | Escalonamento → envio | −70% (efeito dossiê) |
| **Causas extintas** | Ordens de correção com queda confirmada | ≥ 3/mês |
| **Reincidência** | Mesma dúvida, mesma pessoa, 30 dias | queda mês a mês |

## 14.3 Métricas de qualidade e segurança

- Respostas ancoradas em fonte: **100%**
- Alucinação detectada em auditoria: **0%**
- Recall de escalonamento sensível: **≥ 98%**
- **Acerto das previsões das ordens de correção**: mede a credibilidade do Andar 3
- Satisfação do participante (uma pergunta ao fim)

## 14.4 Impacto qualitativo

Disponibilidade 24/7 para quem trava fora do expediente · padronização das orientações · fim do retrabalho por duplicidade entre canais · recuperação de tempo para atividades estratégicas · redução de evasão por barreira técnica.

---

# 15. ESCOPO DO MVP

## ✅ ESSENCIAL

1. Base de conhecimento vetorial com ~15 orientações públicas reais da EMERON
2. Seed de 60 participantes fictícios em estados variados + 3 cursos
3. Assistente com RAG ancorado + resposta personalizada por estado
4. **Guardrail de recusa com escalonamento automático**
5. Motor de eventos com os 5 gatilhos proativos
6. Fluxo guiado de 2FA com verificação por etapa
7. Fila humana com dossiê gerado automaticamente
8. **Contrato de Resolução** (a confirmação "resolveu?")
9. Painel com agrupamento + **1 ordem de correção com previsão**
10. Simulador de WhatsApp + widget do AVA
11. **Modo Ensaio** (ao menos como alternância demonstrável)
12. Identidade progressiva (três níveis visíveis)

## 🎯 DESEJÁVEL

Verificação de efeito da antecipação · aprovação de conhecimento pelo servidor · deduplicação visual entre canais · curva de reincidência · conversão de ligação perdida · validade do conhecimento

## ❌ NÃO CONSTRUIR

Integração real com Moodle/AVA · API oficial do WhatsApp · autenticação real · app móvel nativo · fine-tuning · URA com reconhecimento de voz · gamificação · fórum entre participantes · gráficos adicionais no painel

> **Regra:** se a melhoria adiciona uma tela, desconfie. Se fecha um laço, priorize.

---

# 16. ROADMAP

| Fase | Escopo |
|---|---|
| **Fase 1: Piloto (0, 3 meses)** | Um curso, WhatsApp + widget, Modo Ensaio nas primeiras semanas, liberação categoria por categoria |
| **Fase 2: Consolidação (3, 6 meses)** | Integração real com AVA e base de matrículas, cobertura de e-mail e telefone, grafo da jornada em produção |
| **Fase 3: Expansão (6, 12 meses)** | Espelho do Servidor, multi-setor no TJRO (RH, Corregedoria, suporte), auditoria automática de jornada |
| **Fase 4: Rede (12+ meses)** | Produto para escolas judiciais do país; catálogo compartilhado de causas-raiz |

---

# 17. RISCOS E MITIGAÇÕES

| Risco | Gravidade | Mitigação |
|---|---|---|
| Antecipação virar spam institucional | Alta | Orçamento de atenção + opt-out + desativação automática de gatilho inefetivo |
| Alucinação em ambiente judiciário | Alta | Ancoragem obrigatória, verificação, recusa, escalonamento incondicional de sensíveis, Modo Ensaio |
| Erro silencioso (confiança alta, resposta errada) | Alta | **Contrato de Resolução** captura o caso |
| Conhecimento desatualizado com carimbo oficial | Alta | Validade automática; fonte vencida não responde |
| LGPD / exposição de dado pessoal | Alta | Identidade progressiva, minimização, segregação, log |
| Adoção institucional: ninguém implementar as correções | **Máxima** | Uma ordem por vez, com impacto em atendimentos/mês; Modo Ensaio para construir confiança gradual |
| Partida a frio do Andar 3 | Média | Auditoria da jornada gera valor antes do primeiro atendimento |
| Rejeição por público sênior | Média | WhatsApp como canal de menor atrito; saída humana sempre visível; conversão de ligação perdida |
| Sobrecarga de escalonamento no início | Média | Por design: cada escalonamento vira conhecimento; a curva cai. Honestidade: os primeiros 30 dias dão mais trabalho |
| Dependência de API externa de LLM | Média | Arquitetura agnóstica de provedor; fallback determinístico; caminho para modelo local documentado |
| Escopo grande demais para o hackathon | Alta | Lista ESSENCIAL congelada; nenhuma melhoria adiciona tela nova |

---

# 18. DEFESA PERANTE A BANCA

**"No fim das contas é um chatbot."**
> Um chatbot espera a pergunta, responde igual para todo mundo e responde tudo. O FAROL fala primeiro, responde sobre o caso individual, se recusa quando não tem fonte, **volta depois para verificar se resolveu**, e tem um terceiro andar que elimina a causa. E a EMERON já provou que informar não basta: um chatbot de FAQ seria o quarto banner.

**"Como vocês sabem que a mensagem de vocês não vai falhar como o banner falhou?"**
> Porque nós medimos. Toda mensagem proativa gera uma hipótese verificável: esta pessoa não vai abrir atendimento sobre este assunto em 7 dias. O sistema confere. Gatilho que não funciona é desativado automaticamente. O banner falhou porque ninguém mediu o efeito dele.

**"Por que alguém usaria, se já ignora o banner e o vídeo?"**
> Porque não pedimos mudança de hábito. O banner exige que a pessoa saia do problema para procurar a solução. O FAROL leva a solução até o problema, no WhatsApp que ela já usa, e na maioria das vezes fala primeiro.

**"Por que vocês precisam de IA?"**
> Para exatamente três coisas: entender linguagem natural informal e com erros; recuperar o trecho oficial que fundamenta a resposta; e descobrir agrupamentos de causa que ninguém categorizou. Toda a lógica de decisão, quando escalar, o que é sensível: é regra determinística e auditável. Onde IA não é necessária, não usamos.

**"E se a IA errar?"**
> Preferimos o silêncio ao erro: sem fonte, não responde. E para o erro que nem nós perceberíamos, existe o Contrato de Resolução: o FAROL volta e pergunta se resolveu. Se a pessoa disser que não, ele não repete a resposta: escala, avisando que a orientação padrão falhou.

**"Como vocês conseguiriam os dados?"**
> No hackathon, nenhum: 100% sintéticos, conforme a regra. Em produção, os dados já existem no AVA e na base de matrículas. Construímos os adaptadores com contrato de API definido: a camada mock não é atalho, é a arquitetura correta com implementação trocável.

**"Isso é tecnicamente viável?"**
> Está rodando. Nada aqui é pesquisa: RAG, classificação, scheduler e clusterização são maduros. O trabalho difícil não foi técnico: foi descobrir que o problema não era informação.

**"Quanto custaria?"**
> O custo dominante é consumo de API, na casa de centavos por atendimento. E é a única solução cujo custo **decresce**, porque o terceiro andar reduz a demanda que gera o custo.

**"Como escalar?"**
> A base de conhecimento é conteúdo, não código. Trocando o acervo, o FAROL serve qualquer setor do TJRO ou qualquer escola judicial do país: todas com o mesmo problema e a mesma plataforma.

**"O que impede um concorrente de copiar?"**
> Os dois primeiros andares são copiáveis. O terceiro não, porque não é código: é o laço operacional em que o servidor aprova conhecimento e a instituição implementa correções medidas. Quem copiar a interface leva três dias; quem quiser copiar o efeito precisa de meses de operação acumulada.

**"Qual é o maior risco?"**
> Adoção institucional, não tecnologia. Se ninguém olhar as ordens de correção, o terceiro andar morre. Por isso entregamos **uma** correção por vez, com impacto estimado em atendimentos/mês, e por isso existe o Modo Ensaio: não pedimos confiança, pedimos duas semanas de observação.

**"Não teria sido melhor consertar a plataforma?"**
> Sim. Por isso o terceiro andar existe. Somos a única equipe que entregou a ferramenta que descobre **o que** consertar, com previsão numérica e medição em 30 dias. O atendimento é o alívio imediato; a correção é a cura.

---

# 19. SUPOSIÇÕES DECLARADAS

1. **SUPOSIÇÃO:** o AVA da EMERON é baseado em Moodle. → Confirmar; muda apenas o nome dos adaptadores.
2. **SUPOSIÇÃO:** volume diário de atendimentos e tempo médio por atendimento. → **Obrigatório medir com o setor**; todas as metas devem ser recalculadas com números reais.
3. **SUPOSIÇÃO:** Emeron Play é plataforma de videoaulas complementar ao AVA.
4. **SUPOSIÇÃO:** existe base de matrículas consultável com progresso e situação de certificado.
5. **SUPOSIÇÃO:** distribuição das categorias de dúvida. → Perguntar o ranking real; define o recorte do protótipo.

**Perguntas a fazer à responsável pelo setor no Dia 1:**
Quantos atendimentos por dia, por canal, e tempo médio? · Quais as 10 dúvidas mais frequentes em ordem? · Qual percentual é resolvível sem análise humana? · O que **nunca** deveria ser automatizado? · Qual dúvida mais irrita por ser repetida? · Qual a taxa de abertura do e-mail de boas-vindas? · Que sistema é o AVA e o que expõe via API? · **Se pudesse eliminar uma pergunta para sempre, qual seria?**

> A última é a mais importante: a resposta dela deve virar o exemplo central da demonstração.

---

# SÍNTESE

> **Tudo no FAROL é laço fechado. Ele avisa e verifica se evitou o atendimento. Responde e verifica se resolveu. Aponta a causa e verifica se o volume caiu.**
>
> **É por isso que ele melhora, e é exatamente o que o banner nunca fez.**

**Nome:** FAROL, Fluxo de Atendimento, Resolução e Orientação em Laço
**Slogan:** Responde antes da pergunta. E trabalha para nunca mais precisar responder.
**Tese:** o problema não é falta de informação, está escrito no próprio formulário do desafio.
**Três andares:** Antecipar · Resolver · Extinguir.
**Diferencial:** o único que age antes da pergunta, responde sobre o caso da pessoa, se recusa quando não sabe, confirma se resolveu, e elimina a causa com previsão medida.
**Métrica invertida:** sucesso é ser usado cada vez menos.
