import { useCallback, useEffect, useState } from 'react'
import { BarrasComparadas, BarrasHorizontais } from './componentes/Graficos'
import { Botao, CabecalhoConteudo, TituloSecao, Vazio } from './componentes/Ui'

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
  agrupamento_id: string | null
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
  const medidas = historico.filter((o) => o.resultado_medido !== null)

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
            {/* A ação vem primeiro e sozinha: é a única coisa desta tela que
                alguém precisa DECIDIR. Hipótese e evidência sustentam a
                decisão, e por isso vêm depois dela, não antes. */}
            <p className="text-xs font-bold tracking-wider text-texto-suave uppercase">
              O que fazer
            </p>
            <p className="mt-2 text-xl leading-snug font-semibold text-texto">
              {destaque.acao}
            </p>

            {/* A previsão, do tamanho da aposta que ela é. */}
            <div className="mt-5 grid gap-5 rounded-[--radius-card] bg-superficie-alt p-5 sm:grid-cols-[auto_1fr] sm:items-center">
              <div className="flex items-baseline gap-2">
                <span className="text-5xl leading-none font-bold text-teal">
                  −{destaque.previsao_queda_mensal}
                </span>
                <span className="text-sm leading-tight text-texto-suave">
                  atendimentos
                  <br />
                  por mês
                </span>
              </div>

              <div className="min-w-0">
                <div className="flex items-baseline justify-between gap-3 text-xs text-texto-suave">
                  <span>previsão de queda</span>
                  <span>
                    <strong className="text-texto">
                      {Math.round(
                        (destaque.previsao_queda_mensal /
                          Math.max(1, destaque.volume_base_mensal)) *
                          100,
                      )}
                      %
                    </strong>{' '}
                    da base de {destaque.volume_base_mensal}/mês
                  </span>
                </div>
                {/* A barra mostra a fatia do volume que a correção promete
                    levar. Sem a base ao lado, "−14" não diz se é muito. */}
                <div className="mt-1.5 h-3 overflow-hidden rounded-full bg-superficie">
                  <div
                    className="h-full rounded-full bg-teal transition-[width] duration-700 ease-out"
                    style={{
                      width: `${Math.min(100, (destaque.previsao_queda_mensal / Math.max(1, destaque.volume_base_mensal)) * 100)}%`,
                    }}
                    aria-hidden
                  />
                </div>
                <p className="mt-1.5 text-xs text-texto-suave">
                  Medição automática em 30 dias. Se não cair, a hipótese é
                  descartada.
                </p>
              </div>
            </div>

            <dl className="mt-5 space-y-4 border-t border-borda pt-5">
              <Bloco rotulo="Hipótese" texto={destaque.hipotese} />
              <Bloco rotulo="Evidência" texto={destaque.evidencia} />

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

      {/* Onde o volume está. Barra em vez de lista de cartões: dezesseis
          cartões iguais escondem a única informação que a seção carrega,
          que é qual causa é grande e qual é ruído. */}
      <section className="rounded-[--radius-card] border border-borda bg-superficie p-6">
        <TituloSecao nivel={3}>Onde a demanda se concentra</TituloSecao>
        <p className="mt-2 max-w-3xl text-sm text-texto-suave">
          Agrupamentos por similaridade semântica, não por categoria escolhida
          a dedo. É daqui que sai a próxima ordem de correção.
        </p>

        {radar && radar.agrupamentos.length > 0 ? (
          <div className="mt-5">
            <BarrasHorizontais
              itens={radar.agrupamentos.slice(0, 8).map((g) => ({
                rotulo: g.rotulo,
                valor: g.volume,
                // O agrupamento que originou a ordem em destaque aparece
                // marcado: é o elo entre esta seção e a decisão de cima.
                destacado: g.id === destaque?.agrupamento_id,
                nota: [g.aresta, g.cursos_afetados[0]]
                  .filter(Boolean)
                  .join(' · '),
              }))}
              sufixo=" casos"
            />
            {radar.agrupamentos.length > 8 && (
              <p className="mt-4 text-xs text-texto-suave">
                + {radar.agrupamentos.length - 8} agrupamentos menores, abaixo
                do limiar de ação.
              </p>
            )}
          </div>
        ) : (
          <p className="mt-4 text-sm text-texto-suave">
            Nenhum agrupamento ainda: são necessários ao menos 3 casos
            semelhantes.
          </p>
        )}
      </section>

      {/* O histórico é o que dá credibilidade ao andar inteiro: sem ele, a
          previsão de cima é palpite com aparência de número. */}
      <section className="rounded-[--radius-card] border border-borda bg-superficie p-6">
        <TituloSecao nivel={3}>Previsão contra medição</TituloSecao>

        {medidas.length > 0 ? (
          <>
            <div className="mt-4 flex flex-wrap items-end gap-x-8 gap-y-4">
              <div>
                <p className="text-4xl leading-none font-bold text-azul-titulo">
                  {Math.round((radar?.acerto_das_previsoes.acerto ?? 0) * 100)}%
                </p>
                <p className="mt-1 text-xs text-texto-suave">
                  das previsões acertaram
                </p>
              </div>
              <div className="flex gap-6">
                <div>
                  <p className="text-2xl leading-none font-bold text-sucesso">
                    {radar?.acerto_das_previsoes.causas_extintas ?? 0}
                  </p>
                  <p className="mt-1 text-xs text-texto-suave">causas extintas</p>
                </div>
                <div>
                  <p className="text-2xl leading-none font-bold text-alerta">
                    {radar?.acerto_das_previsoes.hipoteses_descartadas ?? 0}
                  </p>
                  <p className="mt-1 text-xs text-texto-suave">
                    hipóteses descartadas
                  </p>
                </div>
              </div>
            </div>

            <p className="mt-4 max-w-3xl text-sm text-texto-suave">
              A hipótese que erra fica publicada. Uma taxa de acerto que nunca
              mostra erro não está medindo nada.
            </p>

            <div className="mt-5">
              <BarrasComparadas
                itens={medidas.map((o) => ({
                  rotulo: o.acao,
                  previsto: o.previsao_queda_mensal,
                  medido: o.resultado_medido ?? 0,
                  acertou: o.situacao === 'confirmada',
                }))}
              />
            </div>
          </>
        ) : (
          <p className="mt-3 text-sm text-texto-suave">
            Nenhuma previsão medida ainda. A primeira medição acontece 30 dias
            depois de uma ordem ser marcada como implementada.
          </p>
        )}
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
