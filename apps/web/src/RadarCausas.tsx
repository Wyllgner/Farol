import { useCallback, useEffect, useState } from 'react'

type Ordem = {
  id: string
  hipotese: string
  evidencia: string
  acao: string
  previsao_queda_mensal: number
  volume_base_mensal: number
  medir_em: string | null
  implementada_em: string | null
  resultado_medido: number | null
  situacao: string
  conclusao: string | null
  cursos_afetados: string[]
}

type Agrupamento = {
  id: string
  rotulo: string
  volume: number
  cursos_afetados: string[]
  aresta: string | null
}

type Radar = {
  ordem_em_destaque: Ordem | null
  agrupamentos: Agrupamento[]
  acerto_das_previsoes: {
    medidas: number
    acerto: number | null
    causas_extintas?: number
    hipoteses_descartadas?: number
  }
}

export default function RadarCausas() {
  const [radar, setRadar] = useState<Radar | null>(null)
  const [historico, setHistorico] = useState<Ordem[]>([])
  const [ocupado, setOcupado] = useState(false)
  const [aviso, setAviso] = useState<string | null>(null)

  const carregar = useCallback(async () => {
    const [r, h] = await Promise.all([
      fetch('/api/radar').then((x) => x.json()),
      fetch('/api/radar/ordens').then((x) => x.json()),
    ])
    setRadar(r)
    setHistorico(h)
  }, [])

  useEffect(() => {
    carregar()
  }, [carregar])

  async function acao(caminho: string, mensagem: string) {
    setOcupado(true)
    setAviso(null)
    try {
      const r = await fetch(caminho, { method: 'POST' })
      if (!r.ok) throw new Error()
      setAviso(mensagem)
      await carregar()
    } catch {
      setAviso('Não consegui concluir a ação.')
    } finally {
      setOcupado(false)
    }
  }

  const destaque = radar?.ordem_em_destaque ?? null

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium tracking-widest text-dourado-600 uppercase">
            Andar 3 · Extinguir
          </p>
          <h2 className="text-2xl font-semibold text-marinho-900">
            Radar de Causas
          </h2>
          <p className="mt-1 max-w-xl text-sm text-neutro-600">
            Uma correção por vez, com previsão numérica e medição em 30 dias.
            O FAROL não dá palpite — ele volta para dizer se acertou.
          </p>
        </div>
        <button
          disabled={ocupado}
          onClick={() => acao('/api/radar/analisar', 'Análise concluída.')}
          className="rounded-[--radius-suave] bg-marinho-700 px-4 text-white disabled:opacity-40"
        >
          Analisar demandas
        </button>
      </header>

      {aviso && (
        <p role="status" className="text-sm text-marinho-700">
          {aviso}
        </p>
      )}

      {/* A ordem em destaque ocupa a tela. Uma lista de dez itens é uma
          lista que ninguém começa. */}
      {destaque ? (
        <article className="rounded-[--radius-suave] border-2 border-marinho-500 bg-white p-6">
          <p className="text-xs font-semibold tracking-widest text-marinho-700 uppercase">
            Ordem de correção em destaque
          </p>

          <dl className="mt-4 space-y-4">
            <Bloco rotulo="Hipótese" texto={destaque.hipotese} />
            <Bloco rotulo="Evidência" texto={destaque.evidencia} />
            <Bloco rotulo="Ação" texto={destaque.acao} destaque />
            <div>
              <dt className="text-xs font-semibold tracking-wide text-neutro-600 uppercase">
                Previsão
              </dt>
              <dd className="mt-1 text-neutro-900">
                Queda de{' '}
                <strong className="text-2xl text-marinho-900">
                  {destaque.previsao_queda_mensal}
                </strong>{' '}
                atendimentos/mês, sobre uma base de{' '}
                {destaque.volume_base_mensal}.
              </dd>
            </div>
            {destaque.cursos_afetados.length > 0 && (
              <Bloco
                rotulo="Cursos afetados"
                texto={destaque.cursos_afetados.slice(0, 3).join(' · ')}
              />
            )}
          </dl>

          <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-neutro-100 pt-4">
            {destaque.situacao === 'pendente' && (
              <button
                disabled={ocupado}
                onClick={() =>
                  acao(
                    `/api/radar/ordens/${destaque.id}/implementada`,
                    'Marcada como implementada. A medição acontece em 30 dias.',
                  )
                }
                className="rounded-[--radius-suave] bg-marinho-700 px-4 text-white"
              >
                Marcar como implementada
              </button>
            )}
            <button
              disabled={ocupado}
              onClick={() => acao('/api/radar/medir', 'Medição executada.')}
              className="rounded-[--radius-suave] border border-marinho-500 px-4 text-marinho-700"
            >
              Medir agora
            </button>
            <span className="text-sm text-neutro-600">
              Situação: <strong>{destaque.situacao}</strong>
              {destaque.medir_em && ` · medir em ${destaque.medir_em}`}
            </span>
          </div>
        </article>
      ) : (
        <p className="rounded-[--radius-suave] border border-dashed border-neutro-300 p-6 text-neutro-600">
          Nenhuma ordem pendente. Clique em “Analisar demandas” para procurar
          causas nos atendimentos acumulados.
        </p>
      )}

      {/* Gráficos e listas ficam abaixo, secundários. */}
      <section>
        <h3 className="text-sm font-semibold tracking-wide text-neutro-600 uppercase">
          Agrupamentos encontrados
        </h3>
        <ul className="mt-3 space-y-2">
          {radar?.agrupamentos.length === 0 && (
            <li className="text-sm text-neutro-600">
              Nenhum agrupamento ainda — são necessários ao menos 3 casos
              semelhantes.
            </li>
          )}
          {radar?.agrupamentos.map((g) => (
            <li
              key={g.id}
              className="flex items-start justify-between gap-4 rounded-[--radius-suave] border border-neutro-300 bg-white p-3"
            >
              <div>
                <p className="text-neutro-900">{g.rotulo}</p>
                <p className="text-xs text-neutro-600">
                  {g.aresta ? `aresta: ${g.aresta}` : 'aresta não identificada'}
                  {g.cursos_afetados[0] && ` · ${g.cursos_afetados[0]}`}
                </p>
              </div>
              <span className="shrink-0 rounded-full bg-marinho-900 px-2 py-0.5 text-xs text-white">
                {g.volume}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h3 className="text-sm font-semibold tracking-wide text-neutro-600 uppercase">
          Histórico de previsões
        </h3>
        <p className="mt-1 text-sm text-neutro-600">
          {radar?.acerto_das_previsoes.medidas
            ? `${radar.acerto_das_previsoes.causas_extintas ?? 0} causas extintas · ${radar.acerto_das_previsoes.hipoteses_descartadas ?? 0} hipóteses descartadas`
            : 'Nenhuma previsão medida ainda.'}
        </p>
        <ul className="mt-3 space-y-2">
          {historico
            .filter((o) => o.resultado_medido !== null)
            .map((o) => (
              <li
                key={o.id}
                className="rounded-[--radius-suave] border border-neutro-300 bg-white p-3 text-sm"
              >
                <p className="text-neutro-900">{o.hipotese}</p>
                <p className="mt-1 text-neutro-600">{o.conclusao}</p>
              </li>
            ))}
        </ul>
      </section>
    </div>
  )
}

function Bloco({
  rotulo,
  texto,
  destaque,
}: {
  rotulo: string
  texto: string
  destaque?: boolean
}) {
  return (
    <div>
      <dt className="text-xs font-semibold tracking-wide text-neutro-600 uppercase">
        {rotulo}
      </dt>
      <dd
        className={
          destaque
            ? 'mt-1 rounded-[--radius-suave] bg-dourado-400/10 p-3 text-neutro-900'
            : 'mt-1 text-neutro-900'
        }
      >
        {texto}
      </dd>
    </div>
  )
}
