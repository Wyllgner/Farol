import { useCallback, useEffect, useState } from 'react'

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

  const caso = casos.find((c) => c.id === selecionado) ?? null

  return (
    <div className="grid gap-6 lg:grid-cols-[22rem_1fr]">
      <section aria-label="Fila de casos">
        {metricas && (
          <dl className="mb-4 grid grid-cols-2 gap-2 text-sm">
            <Indicador rotulo="Na fila" valor={metricas.na_fila} destaque />
            <Indicador
              rotulo="Orientação falhou"
              valor={metricas.com_orientacao_padrao_falha}
            />
            <Indicador rotulo="Sensíveis" valor={metricas.sensiveis} />
            <Indicador rotulo="Encerrados" valor={metricas.encerrados} />
          </dl>
        )}

        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold tracking-wide text-neutro-600 uppercase">
            Ordenada por consequência
          </h2>
          <button
            onClick={carregar}
            className="text-sm text-marinho-700 underline"
          >
            Atualizar
          </button>
        </div>

        {erro && <p className="mt-3 text-marinho-700">{erro}</p>}

        <ul className="mt-3 space-y-2">
          {casos.length === 0 && !erro && (
            <li className="rounded-[--radius-suave] border border-dashed border-neutro-300 p-4 text-sm text-neutro-600">
              Nada na fila. Sucesso, aqui, é este número ser baixo.
            </li>
          )}

          {casos.map((c) => (
            <li key={c.id}>
              <button
                onClick={() => setSelecionado(c.id)}
                aria-current={c.id === selecionado ? 'true' : undefined}
                className={[
                  'w-full rounded-[--radius-suave] border p-3 text-left',
                  c.id === selecionado
                    ? 'border-marinho-500 bg-marinho-50'
                    : 'border-neutro-300 bg-white',
                ].join(' ')}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-xs font-semibold text-marinho-700 uppercase">
                    {c.categoria}
                  </span>
                  <span className="shrink-0 rounded-full bg-marinho-900 px-2 py-0.5 text-xs text-white">
                    {c.score_consequencia.toFixed(1)}
                  </span>
                </div>

                <p className="mt-1 text-sm text-neutro-900">{c.resumo}</p>

                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                  <Etiqueta>{c.canal}</Etiqueta>
                  <Etiqueta>{c.minutos_esperando} min esperando</Etiqueta>
                  {c.sensivel && <Etiqueta tom="alerta">sensível</Etiqueta>}
                  {c.orientacao_padrao_falhou && (
                    <Etiqueta tom="alerta">orientação falhou</Etiqueta>
                  )}
                  {c.assumido_por && <Etiqueta>{c.assumido_por}</Etiqueta>}
                </div>
              </button>
            </li>
          ))}
        </ul>
      </section>

      {caso ? (
        <DetalheCaso caso={caso} aoMudar={carregar} />
      ) : (
        <section className="grid place-items-center rounded-[--radius-suave] border border-dashed border-neutro-300 p-10 text-neutro-600">
          Selecione um caso para ver o dossiê.
        </section>
      )}
    </div>
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

  return (
    <section className="rounded-[--radius-suave] border border-neutro-300 bg-white p-6">
      {/* Crítico no topo: o dossiê tem de ser lido em 10 segundos. */}
      <p className="text-sm font-medium tracking-widest text-dourado-600 uppercase">
        {caso.categoria} · {caso.canal}
      </p>
      <h2 className="mt-1 text-xl font-semibold text-marinho-900">
        {caso.resumo}
      </h2>

      {caso.orientacao_padrao_falhou && (
        <p className="mt-3 rounded-[--radius-suave] border-l-4 border-dourado-400 bg-dourado-400/10 p-3 text-sm text-neutro-900">
          A orientação padrão já foi entregue e <strong>não resolveu</strong>{' '}
          para esta pessoa. Responder o mesmo de novo não vai adiantar.
        </p>
      )}

      <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
        <Campo rotulo="Motivo do encaminhamento" valor={dossie.motivo_do_escalonamento} />
        <Campo rotulo="Nível de identidade" valor={dossie.nivel_identidade} />
        <Campo rotulo="Confiança" valor={String(dossie.confianca ?? '—')} />
        <Campo rotulo="Espera" valor={`${caso.minutos_esperando} min`} />
      </dl>

      <details className="mt-4 rounded-[--radius-suave] border border-neutro-300 p-3">
        <summary className="cursor-pointer text-sm font-medium text-marinho-700">
          Dossiê completo
        </summary>
        <pre className="mt-3 max-h-80 overflow-auto rounded bg-neutro-50 p-3 text-xs">
          {JSON.stringify(caso.dossie, null, 2)}
        </pre>
      </details>

      <div className="mt-6">
        <label htmlFor="resposta" className="text-sm font-medium text-neutro-600">
          Resposta ao participante
        </label>
        <p className="mb-1 text-xs text-neutro-600">
          Rascunho sugerido. Edite à vontade — nada sai sem sua revisão.
        </p>
        <textarea
          id="resposta"
          rows={6}
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          disabled={encerrado}
          className="w-full rounded-[--radius-suave] border border-neutro-300 p-3 text-base disabled:bg-neutro-100"
        />
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {!caso.assumido_por && !encerrado && (
          <button
            disabled={ocupado}
            onClick={() => acao('assumir', { servidor: SERVIDOR }, 'Caso assumido.')}
            className="rounded-[--radius-suave] border border-marinho-500 px-4 text-marinho-700"
          >
            Assumir
          </button>
        )}

        <button
          disabled={ocupado || encerrado || !texto.trim()}
          onClick={() =>
            acao(
              'responder',
              { servidor: SERVIDOR, texto },
              'Resposta enviada e caso encerrado.',
            )
          }
          className="rounded-[--radius-suave] bg-marinho-700 px-4 text-white disabled:opacity-40"
        >
          Revisar e enviar
        </button>
      </div>

      <div className="mt-6 border-t border-neutro-100 pt-4">
        <h3 className="text-sm font-semibold text-neutro-900">
          Aprovar como conhecimento oficial
        </h3>
        <p className="mt-1 text-xs text-neutro-600">
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
            className="min-h-[44px] flex-1 rounded-[--radius-suave] border border-neutro-300 px-3 text-base"
          />
          <button
            disabled={ocupado || titulo.trim().length < 3 || !texto.trim()}
            onClick={() =>
              acao(
                'aprovar-conhecimento',
                { servidor: SERVIDOR, titulo, conteudo: texto },
                'Conhecimento aprovado e já indexado.',
              )
            }
            className="rounded-[--radius-suave] border border-dourado-600 px-4 text-dourado-600 disabled:opacity-40"
          >
            Aprovar
          </button>
        </div>
      </div>

      {aviso && (
        <p role="status" className="mt-4 text-sm text-marinho-700">
          {aviso}
        </p>
      )}
    </section>
  )
}

function Indicador({
  rotulo,
  valor,
  destaque,
}: {
  rotulo: string
  valor: number
  destaque?: boolean
}) {
  return (
    <div className="rounded-[--radius-suave] border border-neutro-300 bg-white p-3">
      <dt className="text-xs text-neutro-600">{rotulo}</dt>
      <dd
        className={[
          'text-2xl font-semibold',
          destaque ? 'text-marinho-900' : 'text-neutro-600',
        ].join(' ')}
      >
        {valor}
      </dd>
    </div>
  )
}

function Etiqueta({
  children,
  tom,
}: {
  children: React.ReactNode
  tom?: 'alerta'
}) {
  return (
    <span
      className={[
        'rounded-full px-2 py-0.5',
        tom === 'alerta'
          ? 'bg-dourado-400/20 text-dourado-600'
          : 'bg-neutro-100 text-neutro-600',
      ].join(' ')}
    >
      {children}
    </span>
  )
}

function Campo({ rotulo, valor }: { rotulo: string; valor: unknown }) {
  return (
    <>
      <dt className="text-neutro-600">{rotulo}</dt>
      <dd className="text-neutro-900">{String(valor ?? '—')}</dd>
    </>
  )
}
