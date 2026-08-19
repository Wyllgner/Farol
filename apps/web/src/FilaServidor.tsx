import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Botao,
  CabecalhoConteudo,
  Cartao,
  Etiqueta,
  ESTILO_ENTRADA,
  TituloSecao,
  Vazio,
} from './componentes/Ui'

type Caso = {
  id: string
  categoria: string
  canal: string
  sensivel: boolean
  situacao: string
  score_consequencia: number
  orientacao_padrao_falhou: boolean
  contrato_resolucao: string
  resumo: string
  criado_em: string
  minutos_esperando: number
  assumido_por: string | null
  dossie: Record<string, unknown> | null
  rascunho_resposta: string | null
}

type Metricas = {
  na_fila: number
  encerrados: number
  com_orientacao_padrao_falha: number
  sensiveis: number
}

const SERVIDOR = 'Servidora Ana (SECOEAD)'

/**
 * O que o servidor precisa ler primeiro é a PERGUNTA, não o resumo que o
 * sistema gerou sobre ela.
 *
 * O resumo é escrito para a fila ("Fulano: prazo, sem fonte suficiente
 * para responder") e repete a categoria que já está na etiqueta ao lado.
 * Com vinte casos na tela, vinte resumos parecidos viram uma parede
 * cinza: nada distingue um caso do outro, e é preciso abrir todos para
 * saber qual é urgente. A pergunta literal distingue na primeira linha.
 */
function perguntaDe(caso: Caso): string {
  const pergunta = (caso.dossie?.pergunta as string | undefined)?.trim()
  return pergunta || caso.resumo
}

function nomeDe(caso: Caso): string {
  const estado = caso.dossie?.estado_do_participante as
    | { primeiro_nome?: string }
    | undefined
  return estado?.primeiro_nome || 'Anônimo'
}

/**
 * Urgência do caso, na ordem em que a Política de Triagem a define.
 *
 * A fila é ordenada pela consequência de não atender, mas um número solto
 * ("3.0") não diz nada a quem lê. A faixa colorida e o rótulo dizem: são a
 * mesma informação, legível de relance.
 */
type Urgencia = { chave: 'critico' | 'alto' | 'normal'; rotulo: string; barra: string }

function urgenciaDe(caso: Caso): Urgencia {
  if (caso.sensivel || caso.orientacao_padrao_falhou) {
    return { chave: 'critico', rotulo: 'Crítico', barra: 'bg-erro' }
  }
  if (caso.score_consequencia >= 2.5) {
    return { chave: 'alto', rotulo: 'Alta consequência', barra: 'bg-alerta' }
  }
  return { chave: 'normal', rotulo: 'Normal', barra: 'bg-azul' }
}

/** 0.6798 não é linguagem de quem atende. 68% é. */
function porcentagem(valor: unknown): string | null {
  const numero = Number(valor)
  return Number.isFinite(numero) ? `${Math.round(numero * 100)}%` : null
}

function espera(minutos: number): string {
  if (minutos < 60) return `${minutos} min`
  const horas = Math.floor(minutos / 60)
  if (horas < 24) return `${horas} h`
  return `${Math.floor(horas / 24)} d`
}

export default function FilaServidor() {
  const [casos, setCasos] = useState<Caso[]>([])
  const [metricas, setMetricas] = useState<Metricas | null>(null)
  const [selecionado, setSelecionado] = useState<string | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  const carregar = useCallback(async () => {
    try {
      const [f, m] = await Promise.all([
        fetch('/api/fila').then((r) => r.json()),
        fetch('/api/fila/metricas').then((r) => r.json()),
      ])
      setCasos(f)
      setMetricas(m)
      setErro(null)
    } catch {
      setErro('Não consegui carregar a fila.')
    }
  }, [])

  useEffect(() => {
    carregar()
  }, [carregar])

  // Abrir já no primeiro caso: a tela existe para trabalhar a fila, e
  // recebê-la com metade vazia obriga a um clique que não decide nada.
  useEffect(() => {
    if (selecionado === null && casos.length > 0) setSelecionado(casos[0].id)
  }, [casos, selecionado])

  const caso = casos.find((c) => c.id === selecionado) ?? null

  // Dois grupos, não vinte cartões iguais: o que precisa de gente agora e
  // o resto. É a mesma ordenação do backend, só que dita em voz alta.
  const { urgentes, demais } = useMemo(() => {
    const urgentes = casos.filter((c) => urgenciaDe(c).chave !== 'normal')
    return { urgentes, demais: casos.filter((c) => !urgentes.includes(c)) }
  }, [casos])

  return (
    <div className="space-y-5">
      <CabecalhoConteudo
        chapeu="Equipe · SECOEAD"
        titulo="Fila do Servidor"
        descricao="Ordenada pela consequência de não atender, não por ordem de chegada. Nada sai em nome da instituição sem sua revisão."
        acao={
          <Botao tom="secundario" onClick={carregar}>
            Atualizar
          </Botao>
        }
      />

      {metricas && <Placar metricas={metricas} />}

      <div className="grid items-start gap-5 xl:grid-cols-[23rem_1fr]">
        {/* A lista rola dentro da propria coluna. Sem isso as duas colunas
            disputam a mesma barra de rolagem: para ver o caso 12 o
            servidor tinha de empurrar o dossie inteiro para fora da tela. */}
        <section
          aria-label="Casos"
          className="space-y-5 xl:max-h-[calc(100vh-11rem)] xl:overflow-y-auto xl:pr-1"
        >
          {erro && <p className="text-sm text-erro">{erro}</p>}

          {casos.length === 0 && !erro && (
            <Vazio>Nada na fila. Sucesso, aqui, é este número ser baixo.</Vazio>
          )}

          <Grupo
            titulo="Precisam de você agora"
            casos={urgentes}
            selecionado={selecionado}
            aoSelecionar={setSelecionado}
          />
          <Grupo
            titulo="Demais casos"
            casos={demais}
            selecionado={selecionado}
            aoSelecionar={setSelecionado}
          />
        </section>

        {caso ? (
          <div className="xl:sticky xl:top-[5.5rem]">
            <DetalheCaso caso={caso} aoMudar={carregar} />
          </div>
        ) : (
          <Cartao>
            <p className="py-16 text-center text-sm text-texto-suave">
              Escolha um caso à esquerda para abrir o dossiê.
            </p>
          </Cartao>
        )}
      </div>
    </div>
  )
}

/** Placar em faixa. Quatro caixotes com três zeros ocupavam a tela toda. */
function Placar({ metricas }: { metricas: Metricas }) {
  const itens: { rotulo: string; valor: number; alerta?: boolean }[] = [
    { rotulo: 'Na fila', valor: metricas.na_fila },
    {
      rotulo: 'Orientação falhou',
      valor: metricas.com_orientacao_padrao_falha,
      alerta: metricas.com_orientacao_padrao_falha > 0,
    },
    { rotulo: 'Sensíveis', valor: metricas.sensiveis, alerta: metricas.sensiveis > 0 },
    { rotulo: 'Encerrados', valor: metricas.encerrados },
  ]

  return (
    <dl className="flex flex-wrap items-center gap-x-8 gap-y-3 rounded-[--radius-card] border border-borda bg-superficie px-5 py-3">
      {itens.map(({ rotulo, valor, alerta }) => (
        <div key={rotulo} className="flex items-baseline gap-2">
          <dd
            className={[
              'text-2xl font-bold tabular-nums',
              alerta ? 'text-alerta' : 'text-azul-titulo',
            ].join(' ')}
          >
            {valor}
          </dd>
          <dt className="text-sm text-texto-suave">{rotulo}</dt>
        </div>
      ))}
    </dl>
  )
}

function Grupo({
  titulo,
  casos,
  selecionado,
  aoSelecionar,
}: {
  titulo: string
  casos: Caso[]
  selecionado: string | null
  aoSelecionar: (id: string) => void
}) {
  if (casos.length === 0) return null

  return (
    <div>
      <div className="flex items-center gap-3">
        <TituloSecao nivel={3}>{titulo}</TituloSecao>
        <span className="shrink-0 text-sm font-semibold text-texto-suave tabular-nums">
          {casos.length}
        </span>
      </div>

      <ul className="mt-3 space-y-2">
        {casos.map((c) => (
          <li key={c.id}>
            <CartaoDeCaso
              caso={c}
              ativo={c.id === selecionado}
              aoSelecionar={() => aoSelecionar(c.id)}
            />
          </li>
        ))}
      </ul>
    </div>
  )
}

function CartaoDeCaso({
  caso,
  ativo,
  aoSelecionar,
}: {
  caso: Caso
  ativo: boolean
  aoSelecionar: () => void
}) {
  const urgencia = urgenciaDe(caso)

  return (
    <button
      onClick={aoSelecionar}
      aria-current={ativo ? 'true' : undefined}
      className={[
        'flex w-full gap-0 overflow-hidden rounded-[--radius-controle] border bg-superficie text-left transition-colors',
        ativo
          ? 'border-azul ring-1 ring-azul'
          : 'border-borda hover:border-azul/40 hover:shadow-sm',
      ].join(' ')}
    >
      {/* Faixa de urgência: cor é o que se lê antes de qualquer palavra. */}
      <span
        className={`w-1.5 shrink-0 self-stretch ${urgencia.barra}`}
        aria-hidden
      />

      <span className="min-w-0 flex-1 px-3.5 py-3">
        <span className="flex items-baseline justify-between gap-2">
          <span className="truncate text-sm font-semibold text-texto">
            {nomeDe(caso)}
          </span>
          <span className="shrink-0 text-xs text-texto-suave tabular-nums">
            {espera(caso.minutos_esperando)}
          </span>
        </span>

        {/* A pergunta da pessoa, que é o que distingue um caso do outro. */}
        <span className="mt-1 line-clamp-2 block text-sm leading-snug text-texto-suave">
          {perguntaDe(caso)}
        </span>

        <span className="mt-2 flex flex-wrap items-center gap-1">
          <Etiqueta>{caso.categoria}</Etiqueta>
          {/* A categoria "sensivel" ja diz que e sensivel: repetir a palavra
              em duas etiquetas lado a lado parecia defeito de renderizacao.
              A marca so acrescenta quando o assunto e outro e a politica
              escalou mesmo assim. */}
          {caso.sensivel && caso.categoria !== 'sensivel' && (
            <Etiqueta tom="alerta">sensível</Etiqueta>
          )}
          {caso.orientacao_padrao_falhou && (
            <Etiqueta tom="alerta">orientação falhou</Etiqueta>
          )}
          {caso.assumido_por && <Etiqueta tom="azul">assumido</Etiqueta>}
        </span>
      </span>
    </button>
  )
}

function DetalheCaso({ caso, aoMudar }: { caso: Caso; aoMudar: () => void }) {
  const [texto, setTexto] = useState(caso.rascunho_resposta ?? '')
  const [titulo, setTitulo] = useState('')
  const [aviso, setAviso] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState(false)

  useEffect(() => {
    setTexto(caso.rascunho_resposta ?? '')
    setTitulo('')
    setAviso(null)
  }, [caso.id, caso.rascunho_resposta])

  async function acao(caminho: string, corpo: object, mensagem: string) {
    setOcupado(true)
    try {
      const r = await fetch(`/api/fila/${caso.id}/${caminho}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(corpo),
      })
      if (!r.ok) throw new Error(await r.text())
      setAviso(mensagem)
      aoMudar()
    } catch {
      setAviso('Não consegui concluir a ação.')
    } finally {
      setOcupado(false)
    }
  }

  const dossie = caso.dossie ?? {}
  const encerrado = caso.situacao === 'encerrado'
  const urgencia = urgenciaDe(caso)

  return (
    <Cartao>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-bold tracking-[0.16em] text-texto-suave uppercase">
            {nomeDe(caso)} · {caso.categoria} · {caso.canal}
          </p>
          {/* A pergunta é o título: é sobre ela que a pessoa espera resposta. */}
          <h2 className="mt-1 text-xl font-bold text-texto">{perguntaDe(caso)}</h2>
        </div>
        <Etiqueta tom={urgencia.chave === 'normal' ? undefined : 'alerta'}>
          {urgencia.rotulo}
        </Etiqueta>
      </div>
      <div className="mt-3 h-0.5 w-20 bg-ciano" aria-hidden />

      {caso.orientacao_padrao_falhou && (
        <p className="mt-4 rounded-[--radius-controle] border-l-4 border-alerta bg-alerta/5 p-3 text-sm">
          A orientação padrão já foi entregue e <strong>não resolveu</strong> para
          esta pessoa. Responder o mesmo de novo não vai adiantar.
        </p>
      )}

      <dl className="mt-5 grid gap-x-8 gap-y-4 rounded-[--radius-controle] bg-superficie-alt p-4 sm:grid-cols-2">
        <Campo rotulo="Motivo do encaminhamento" valor={dossie.motivo_do_escalonamento} />
        <Campo rotulo="Nível de identidade" valor={dossie.nivel_identidade} />
        <Campo rotulo="Confiança" valor={porcentagem(dossie.confianca)} />
        <Campo rotulo="Espera" valor={espera(caso.minutos_esperando)} />
      </dl>

      <Dossie dossie={dossie} />

      <div className="mt-6">
        <label htmlFor="resposta" className="text-sm font-semibold text-azul-titulo">
          Resposta ao participante
        </label>
        <p className="mb-1 text-xs text-texto-suave">
          Rascunho sugerido. Edite à vontade: nada sai sem sua revisão.
        </p>
        <textarea
          id="resposta"
          rows={6}
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          disabled={encerrado}
          className={`${ESTILO_ENTRADA} py-2 disabled:bg-superficie-alt`}
        />
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {!caso.assumido_por && !encerrado && (
          <Botao
            tom="secundario"
            disabled={ocupado}
            onClick={() => acao('assumir', { servidor: SERVIDOR }, 'Caso assumido.')}
          >
            Assumir
          </Botao>
        )}

        <Botao
          disabled={ocupado || encerrado || !texto.trim()}
          onClick={() =>
            acao(
              'responder',
              { servidor: SERVIDOR, texto },
              'Resposta enviada e caso encerrado.',
            )
          }
        >
          Revisar e enviar
        </Botao>
      </div>

      <div className="mt-6 border-t border-borda pt-4">
        <TituloSecao nivel={3}>Aprovar como conhecimento</TituloSecao>
        <p className="mt-2 text-xs text-texto-suave">
          A resposta entra na base, passa a ser citável como fonte, e casos
          semelhantes deixam de escalar.
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          <label htmlFor="titulo" className="sr-only">
            Título do documento
          </label>
          <input
            id="titulo"
            value={titulo}
            onChange={(e) => setTitulo(e.target.value)}
            placeholder="Título do documento"
            className={`${ESTILO_ENTRADA} flex-1`}
          />
          <Botao
            tom="secundario"
            disabled={ocupado || titulo.trim().length < 3 || !texto.trim()}
            onClick={() =>
              acao(
                'aprovar-conhecimento',
                { servidor: SERVIDOR, titulo, conteudo: texto },
                'Conhecimento aprovado e já indexado.',
              )
            }
          >
            Aprovar
          </Botao>
        </div>
      </div>

      {aviso && (
        <p role="status" className="mt-4 text-sm font-medium text-sucesso">
          {aviso}
        </p>
      )}
    </Cartao>
  )
}

function Campo({ rotulo, valor }: { rotulo: string; valor: unknown }) {
  const vazio = valor === null || valor === undefined || valor === ''
  return (
    <div className="min-w-0">
      <dt className="text-[0.6875rem] font-semibold tracking-[0.12em] text-texto-suave uppercase">
        {rotulo}
      </dt>
      <dd
        className={[
          'mt-1 text-sm',
          vazio ? 'text-texto-suave' : 'font-medium text-texto',
        ].join(' ')}
      >
        {vazio ? '—' : String(valor)}
      </dd>
    </div>
  )
}


// --------------------------------------------------------------------------
// Dossiê
// --------------------------------------------------------------------------

type CursoDoEstado = {
  curso: string
  progresso_pct: number
  nunca_acessou: boolean
  dias_desde_ultimo_acesso: number | null
  dois_fatores_configurado: boolean
  dias_ate_o_prazo: number | null
  situacao_certificado: string
}

type EstadoDoParticipante = {
  primeiro_nome?: string
  perfil?: string
  cursos?: CursoDoEstado[]
}

type FonteConsultada = { documento: string; dono: string; score: number }

const CERTIFICADO_EM_PORTUGUES: Record<string, string> = {
  nao_elegivel: 'certificado ainda não liberado',
  liberado: 'certificado liberado para emissão',
  emitido: 'certificado já emitido',
}

/**
 * O dossiê como texto, e não como JSON.
 *
 * Quem abre esta tela é um servidor da SECOEAD decidindo o que responder a
 * uma pessoa, não alguém depurando o sistema. Um bloco de JSON obriga a
 * traduzir `dois_fatores_configurado: false` mentalmente antes de pensar
 * no caso, e some com a informação importante no meio de chaves e
 * vírgulas. Os mesmos dados, escritos em português, cabem em dez segundos
 * de leitura, que é o tempo que o dossiê tem para valer a pena.
 *
 * Os dados brutos continuam ali embaixo: o compromisso de auditabilidade é
 * mostrar tudo, não é mostrar feio.
 */
function Dossie({ dossie }: { dossie: Record<string, unknown> }) {
  const estado = dossie.estado_do_participante as EstadoDoParticipante | undefined
  const fontes = (dossie.fontes_consultadas as FonteConsultada[] | undefined) ?? []
  const ancoragem = dossie.ancoragem as
    | { intacta: boolean; motivo: string }
    | undefined
  const naoCompreendida = dossie.resposta_que_nao_foi_compreendida as
    | string
    | undefined
  const transcricao = (dossie.transcricao as Turno[] | undefined) ?? []

  return (
    <section className="mt-5 rounded-[--radius-card] border border-borda">
      <div className="border-b border-borda bg-superficie-alt px-4 py-2.5">
        <TituloSecao nivel={3}>Dossiê</TituloSecao>
      </div>
      <div className="divide-y divide-borda">

      {/* A conversa vem primeiro. Uma pergunta solta e ilegivel: "e o meu?"
          nao significa nada sem os dois turnos anteriores, e o servidor
          reconstruia de cabeca o que o sistema ja tinha registrado. */}
      {transcricao.length > 0 && (
        <Bloco titulo={`Conversa (${transcricao.length} mensagens)`}>
          <Transcricao turnos={transcricao} />
        </Bloco>
      )}

      {estado?.cursos?.length ? (
        <Bloco
          titulo={`Situação de ${estado.primeiro_nome ?? 'quem perguntou'}${
            estado.perfil ? ` · ${estado.perfil}` : ''
          }`}
        >
          <ul className="space-y-3">
            {estado.cursos.map((curso) => (
              <li key={curso.curso}>
                <p className="text-sm font-semibold text-texto">{curso.curso}</p>
                {/* Um fato por linha, e nao tudo numa frase so: o servidor
                    procura UM deles, e a leitura corrida obriga a ler todos. */}
                <ul className="mt-1.5 flex flex-wrap gap-x-2 gap-y-1">
                  {fatosDoCurso(curso).map((fato) => (
                    <li key={fato}>
                      <Etiqueta>{fato}</Etiqueta>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </Bloco>
      ) : (
        <Bloco titulo="Situação do participante">
          <p className="text-sm text-texto-suave">
            Pessoa não identificada no canal: o dossiê não tem estado
            individual.
          </p>
        </Bloco>
      )}

      {naoCompreendida && (
        <Bloco titulo="Resposta que não foi compreendida">
          <p className="border-l-2 border-alerta pl-3 text-sm text-texto italic">
            {naoCompreendida}
          </p>
        </Bloco>
      )}

      {fontes.length > 0 && (
        <Bloco titulo="Fontes consultadas">
          <ul className="space-y-1.5 text-sm">
            {fontes.map((fonte) => (
              <li
                key={fonte.documento}
                className="flex items-baseline justify-between gap-3"
              >
                <span className="min-w-0">
                  <span className="text-texto">{fonte.documento}</span>{' '}
                  <span className="text-xs text-texto-suave">{fonte.dono}</span>
                </span>
                <span className="shrink-0 text-xs text-texto-suave tabular-nums">
                  {porcentagem(fonte.score)} de aderência
                </span>
              </li>
            ))}
          </ul>
        </Bloco>
      )}

      {ancoragem && (
        <Bloco titulo="Verificação de ancoragem">
          <p className="flex flex-wrap items-center gap-2 text-sm">
            <Etiqueta tom={ancoragem.intacta ? 'sucesso' : 'alerta'}>
              {ancoragem.intacta ? 'íntegra' : 'bloqueada'}
            </Etiqueta>
            <span className="text-texto-suave">{ancoragem.motivo}</span>
          </p>
        </Bloco>
      )}

      {/* Auditabilidade nao negociavel: o registro cru continua a um clique. */}
      <details className="px-4 py-3">
        <summary className="cursor-pointer text-xs font-semibold text-azul-titulo">
          Ver registro completo
        </summary>
        <pre className="mt-3 max-h-80 overflow-auto rounded bg-superficie-alt p-3 text-xs">
          {JSON.stringify(dossie, null, 2)}
        </pre>
      </details>
      </div>
    </section>
  )
}

type Turno = {
  quem: 'participante' | 'farol'
  canal: string
  texto: string
  em: string | null
  entregue: boolean
}

const NOME_DO_CANAL: Record<string, string> = {
  whatsapp: 'WhatsApp',
  widget_ava: 'Widget do AVA',
  email: 'E-mail',
  telefone: 'Telefone',
}

/**
 * A conversa consolidada, do começo para o fim.
 *
 * Alinhada como um chat de propósito: o servidor precisa reconhecer num
 * relance quem disse o quê, e uma lista de parágrafos iguais obrigaria a
 * ler rótulo por rótulo.
 *
 * O canal aparece em cada turno porque a transcrição é unificada: a mesma
 * pessoa começa no widget e continua no WhatsApp, e saber onde cada coisa
 * foi dita muda como o servidor responde.
 */
function Transcricao({ turnos }: { turnos: Turno[] }) {
  return (
    <ol className="space-y-2.5">
      {turnos.map((t, i) => {
        const daPessoa = t.quem === 'participante'
        return (
          <li
            key={`${t.em ?? i}-${i}`}
            className={daPessoa ? 'pr-8' : 'pl-8'}
          >
            <div
              className={[
                'rounded-[--radius-card] border px-3 py-2',
                daPessoa
                  ? 'border-borda bg-superficie-alt'
                  : 'border-azul-100 bg-azul-100/40',
              ].join(' ')}
            >
              <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-texto-suave">
                <span className="font-semibold text-texto">
                  {daPessoa ? 'Participante' : 'FAROL'}
                </span>
                <span>· {NOME_DO_CANAL[t.canal] ?? t.canal}</span>
                {t.em && <span>· {new Date(t.em).toLocaleString('pt-BR')}</span>}
                {/* Proativa na fila ainda não foi lida por ninguém. Sem esta
                    marca, o servidor supõe que a pessoa já recebeu a
                    orientação e responde como se ela tivesse ignorado. */}
                {!t.entregue && <Etiqueta tom="alerta">não entregue</Etiqueta>}
              </p>
              <p className="mt-1 text-sm whitespace-pre-line text-texto">
                {t.texto}
              </p>
            </div>
          </li>
        )
      })}
    </ol>
  )
}

/** Traduz o estado da matrícula para frases que um servidor lê direto. */
function fatosDoCurso(curso: CursoDoEstado): string[] {
  const fatos = [`progresso ${Math.round(curso.progresso_pct)}%`]

  fatos.push(
    curso.nunca_acessou
      ? 'nunca acessou'
      : curso.dias_desde_ultimo_acesso === null
        ? 'já acessou'
        : `último acesso há ${curso.dias_desde_ultimo_acesso} dias`,
  )

  fatos.push(
    curso.dois_fatores_configurado ? '2FA configurado' : '2FA não configurado',
  )

  if (curso.dias_ate_o_prazo !== null) {
    fatos.push(
      curso.dias_ate_o_prazo < 0
        ? `prazo vencido há ${Math.abs(curso.dias_ate_o_prazo)} dias`
        : `faltam ${curso.dias_ate_o_prazo} dias para o prazo`,
    )
  }

  fatos.push(
    CERTIFICADO_EM_PORTUGUES[curso.situacao_certificado] ??
      'situação do certificado indefinida',
  )

  return fatos
}

/** Faixa do dossiê: rótulo pequeno em cima, conteúdo com ar embaixo. */
function Bloco({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div className="px-4 py-3.5">
      <p className="text-[0.6875rem] font-semibold tracking-[0.12em] text-texto-suave uppercase">
        {titulo}
      </p>
      <div className="mt-2">{children}</div>
    </div>
  )
}
