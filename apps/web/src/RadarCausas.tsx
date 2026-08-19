import { useCallback, useEffect, useState } from 'react'
import {
  Botao,
  CabecalhoConteudo,
  Etiqueta,
  TituloSecao,
  Vazio,
} from './componentes/Ui'

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
    <div className="space-y-6">
      <CabecalhoConteudo
        chapeu="Gestão · Extinguir a causa"
        titulo="Radar de Causas"
        descricao="Uma correção por vez, com previsão numérica e medição em 30 dias. O FAROL não dá palpite: ele volta para dizer se acertou."
        acao={
          <Botao
            tom="secundario"
            disabled={ocupado}
            onClick={() => acao('/api/radar/analisar', 'Análise concluída.')}
          >
            Analisar demandas
          </Botao>
        }
      />

      {aviso && (
        <p role="status" className="text-sm font-medium text-sucesso">
          {aviso}
        </p>
      )}

      {/* A ordem em destaque ocupa a tela. Teal: é trabalho proativo. */}
      {destaque ? (
        <article className="overflow-hidden rounded-[--radius-card] border-2 border-teal bg-superficie">
          <div className="bg-teal px-6 py-3 text-sobre-azul">
            <p className="text-xs font-bold tracking-[0.16em] uppercase">
              Ordem de correção em destaque
            </p>
          </div>

          <div className="p-6">
            <dl className="space-y-4">
              <Bloco rotulo="Hipótese" texto={destaque.hipotese} />
              <Bloco rotulo="Evidência" texto={destaque.evidencia} />
              <Bloco rotulo="Ação" texto={destaque.acao} destaque />

              <div>
                <dt className="text-xs font-bold tracking-wider text-texto-suave uppercase">
                  Previsão
                </dt>
                <dd className="mt-1 flex flex-wrap items-baseline gap-2">
                  <span className="text-4xl font-bold text-teal">
                    −{destaque.previsao_queda_mensal}
                  </span>
                  <span className="text-texto">
                    atendimentos/mês, sobre uma base de{' '}
                    {destaque.volume_base_mensal}.
                  </span>
                </dd>
                <dd className="mt-2 h-2 overflow-hidden rounded-full bg-superficie-alt">
                  {/* Barra de progresso: acento ciano. */}
                  <div
                    className="h-full rounded-full bg-ciano"
                    style={{
                      width: `${Math.min(100, (destaque.previsao_queda_mensal / Math.max(1, destaque.volume_base_mensal)) * 100)}%`,
                    }}
                    aria-hidden
                  />
                </dd>
              </div>

              {destaque.cursos_afetados.length > 0 && (
                <Bloco
                  rotulo="Cursos afetados"
                  texto={destaque.cursos_afetados.slice(0, 3).join(' · ')}
                />
              )}
            </dl>

            <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-borda pt-4">
              {destaque.situacao === 'pendente' && (
                <Botao
                  tom="proativo"
                  disabled={ocupado}
                  onClick={() =>
                    acao(
                      `/api/radar/ordens/${destaque.id}/implementada`,
                      'Marcada como implementada. A medição acontece em 30 dias.',
                    )
                  }
                >
                  Marcar como implementada
                </Botao>
              )}
              <Botao
                tom="secundario"
                disabled={ocupado}
                onClick={() => acao('/api/radar/medir', 'Medição executada.')}
              >
                Medir agora
              </Botao>
              <span className="text-sm text-texto-suave">
                Situação: <strong className="text-texto">{destaque.situacao}</strong>
                {destaque.medir_em && ` · medir em ${destaque.medir_em}`}
              </span>
            </div>
          </div>
        </article>
      ) : (
        <Vazio>
          Nenhuma ordem pendente. Clique em “Analisar demandas” para procurar
          causas nos atendimentos acumulados.
        </Vazio>
      )}

      {/* Listas ficam abaixo, secundárias. */}
      <section>
        <TituloSecao nivel={3}>Agrupamentos encontrados</TituloSecao>
        <ul className="mt-3 space-y-2">
          {radar?.agrupamentos.length === 0 && (
            <li className="text-sm text-texto-suave">
              Nenhum agrupamento ainda: são necessários ao menos 3 casos
              semelhantes.
            </li>
          )}
          {radar?.agrupamentos.map((g) => (
            <li
              key={g.id}
              className="flex items-start justify-between gap-4 rounded-[--radius-card] border border-borda bg-superficie p-3"
            >
              <div className="min-w-0">
                <p className="text-texto">{g.rotulo}</p>
                <p className="mt-1 flex flex-wrap gap-1.5">
                  <Etiqueta tom="proativo">
                    {g.aresta ?? 'aresta não identificada'}
                  </Etiqueta>
                  {g.cursos_afetados[0] && <Etiqueta>{g.cursos_afetados[0]}</Etiqueta>}
                </p>
              </div>
              <span className="shrink-0 rounded-full bg-teal px-2.5 py-0.5 text-xs font-semibold text-sobre-azul">
                {g.volume}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <TituloSecao nivel={3}>Histórico de previsões</TituloSecao>
        <p className="mt-2 text-sm text-texto-suave">
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
                className="rounded-[--radius-card] border border-borda bg-superficie p-3 text-sm"
              >
                <p className="text-texto">{o.hipotese}</p>
                <p
                  className={`mt-1 ${o.situacao === 'confirmada' ? 'text-sucesso' : 'text-alerta'}`}
                >
                  {o.conclusao}
                </p>
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
      <dt className="text-xs font-bold tracking-wider text-texto-suave uppercase">
        {rotulo}
      </dt>
      <dd
        className={
          destaque
            ? 'mt-1 rounded-[--radius-controle] bg-azul-100 p-3 text-texto'
            : 'mt-1 text-texto'
        }
      >
        {texto}
      </dd>
    </div>
  )
}
