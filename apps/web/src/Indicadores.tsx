import { useEffect, useState } from 'react'
import { CabecalhoConteudo, TituloSecao } from './componentes/Ui'
import {
  BarraEmpilhada,
  BarrasComparadas,
  GraficoLinhas,
  Legenda,
  Sparkline,
} from './componentes/Graficos'
import { corDaSerie } from './componentes/paleta'

type Dados = {
  atendimentos_evitados: number
  horas_devolvidas_a_equipe: number
  causas_extintas: number
  taxa_antecipacao_efetiva: number | null
  taxa_resolucao_sem_humano: number | null
  taxa_confirmacao_resolucao: number | null
  acerto_das_previsoes: number | null
  total_de_casos: number
  na_fila: number
  respostas_sem_fonte: number
}

type Series = {
  semanas: string[]
  ate: string
  volume: {
    chegaram: number[]
    evitados: number[]
    refutados: number[]
    resolvidos_sem_humano: number[]
    escalados: number[]
  }
  por_categoria: { categoria: string; valores: number[] }[]
  ordens_medidas: {
    acao: string
    previsto: number
    medido: number
    acertou: boolean
  }[]
  destino_dos_casos: { decisao: string; total: number }[]
}

function pct(v: number | null): string {
  return v === null ? '—' : `${Math.round(v * 100)}%`
}

const NOME_DA_DECISAO: Record<string, string> = {
  responde: 'Respondeu sozinho',
  responde_com_oferta_humana: 'Respondeu e ofereceu humano',
  escala: 'Escalou para servidor',
}

const NOME_DA_CATEGORIA: Record<string, string> = {
  '2fa': 'Segundo fator (2FA)',
  webconferencia: 'Webconferência',
  certificado: 'Certificado',
  prazo: 'Prazo',
  senha: 'Senha',
  acesso: 'Acesso',
  localizacao_curso: 'Localização do curso',
  conteudo: 'Conteúdo',
  inscricao: 'Inscrição',
  reclamacao: 'Reclamação',
  outras: 'Demais categorias',
}

/**
 * Data ISO em pt-BR sem passar pelo fuso.
 *
 * `new Date('2026-08-17')` e interpretado como meia-noite UTC, que no
 * Brasil ainda e dia 16: a legenda mostrava um dia a menos que a serie.
 */
function dataBr(iso: string): string {
  const [ano, mes, dia] = iso.split('-')
  return `${dia}/${mes}/${ano}`
}

/** Variação entre a primeira e a última semana da série. */
function variacao(valores: number[]): number | null {
  const inicio = valores[0]
  const fim = valores[valores.length - 1]
  if (!inicio) return null
  return (fim - inicio) / inicio
}

export default function Indicadores() {
  const [d, setDados] = useState<Dados | null>(null)
  const [s, setSeries] = useState<Series | null>(null)
  const [tabela, setTabela] = useState(false)

  useEffect(() => {
    fetch('/api/indicadores')
      .then((r) => r.json())
      .then(setDados)
      .catch(() => setDados(null))
    fetch('/api/indicadores/series')
      .then((r) => r.json())
      .then(setSeries)
      .catch(() => setSeries(null))
  }, [])

  if (!d) return <p className="text-texto-suave">Carregando indicadores…</p>

  const quedaTotal = s ? variacao(s.volume.chegaram) : null

  return (
    <div className="space-y-8">
      <CabecalhoConteudo
        chapeu="Gestão · Métrica invertida"
        titulo="Sucesso, aqui, é este painel diminuir"
        descricao="Todo painel de chatbot comemora quando o número de conversas sobe. O do FAROL comemora quando desce, porque significa que as causas estão sendo eliminadas."
      />

      {/* A métrica invertida vem primeiro, grande, sozinha. */}
      <section className="grid gap-4 sm:grid-cols-3">
        <Grande
          rotulo="Atendimentos evitados"
          valor={String(d.atendimentos_evitados)}
          nota="comprovados por hipótese verificada"
          serie={s?.volume.evitados}
          cor="var(--serie-1)"
        />
        <Grande
          rotulo="Horas devolvidas à equipe"
          valor={`${d.horas_devolvidas_a_equipe}h`}
          nota="tempo que voltou para o trabalho estratégico"
          serie={s?.volume.evitados}
          cor="var(--serie-3)"
        />
        <Grande
          rotulo="Causas extintas"
          valor={String(d.causas_extintas)}
          nota="correções com queda confirmada"
          // Este cartão não tem série no tempo: causa extinta é evento
          // raro e discreto, e uma linha de quatro pontos seria ruído
          // com cara de tendência. Os selos mostram o placar real das
          // ordens medidas, inclusive a que falhou.
          selos={s?.ordens_medidas.map((o) => o.acertou)}
        />
      </section>

      {/* O gráfico que sustenta a tese: as duas curvas se cruzando. */}
      {s && (
        <section className="rounded-[--radius-card] border border-borda bg-superficie p-6">
          <TituloSecao nivel={3}>A curva que precisa descer</TituloSecao>
          <p className="mt-3 max-w-3xl text-sm text-texto-suave">
            Atendimentos que chegaram à equipe, semana a semana, contra
            atendimentos evitados pelo Andar 1. O cruzamento das duas linhas é a
            tese do FAROL acontecendo:{' '}
            {quedaTotal !== null && quedaTotal < 0 ? (
              <>
                o volume que chega caiu{' '}
                <strong className="text-texto">
                  {Math.abs(Math.round(quedaTotal * 100))}%
                </strong>{' '}
                nas {s.semanas.length} semanas do período.
              </>
            ) : (
              <>o período ainda não fechou queda.</>
            )}
          </p>

          {/* Sem caixa de legenda: cada curva carrega o próprio rótulo na
              ponta direita, que é onde o olho já está quando termina de
              seguir a linha. */}
          <div className="mt-5">
            <GraficoLinhas
              rotulos={s.semanas}
              series={[
                {
                  rotulo: 'chegaram à equipe',
                  valores: s.volume.chegaram,
                  cor: 'var(--serie-1)',
                  area: true,
                },
                {
                  rotulo: 'evitados',
                  valores: s.volume.evitados,
                  cor: 'var(--serie-2)',
                },
              ]}
            />
          </div>

          <p className="mt-2 text-xs text-texto-suave">
            Semanas fechadas, até {dataBr(s.ate)}. A
            semana em curso não entra: com dois dias de dado onde as outras têm
            sete, ela desenharia uma queda que não aconteceu.
          </p>
        </section>
      )}

      {/* Onde a queda aconteceu, categoria por categoria. */}
      {s && (
        <section className="rounded-[--radius-card] border border-borda bg-superficie p-6">
          <TituloSecao nivel={3}>Onde o volume caiu</TituloSecao>
          <p className="mt-3 max-w-3xl text-sm text-texto-suave">
            Mesma escala em todos os quadros. As duas categorias que receberam
            ordem de correção são as que despencam — as outras seguem no patamar
            de sempre, o que é a prova de que a queda não foi movimento geral.
          </p>

          <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {s.por_categoria.map((c, i) => {
              const v = variacao(c.valores)
              const maximo = Math.max(
                ...s.por_categoria.flatMap((x) => x.valores),
              )
              return (
                <div
                  key={c.categoria}
                  className="rounded-[--radius-controle] border border-borda p-3"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <p className="truncate text-xs font-semibold text-texto">
                      {NOME_DA_CATEGORIA[c.categoria] ?? c.categoria}
                    </p>
                    {v !== null && (
                      <span
                        className={[
                          'shrink-0 text-xs font-bold',
                          v < 0 ? 'text-sucesso' : 'text-texto-suave',
                        ].join(' ')}
                      >
                        {v > 0 ? '+' : ''}
                        {Math.round(v * 100)}%
                      </span>
                    )}
                  </div>
                  <Sparkline
                    valores={c.valores}
                    cor={corDaSerie(i, c.categoria)}
                    maximo={maximo}
                  />
                  <p className="text-[11px] text-texto-suave">
                    {c.valores[0]} → {c.valores[c.valores.length - 1]} casos/semana
                  </p>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* Andar 3: a previsão contra a régua. */}
      {s && s.ordens_medidas.length > 0 && (
        <section className="rounded-[--radius-card] border border-borda bg-superficie p-6">
          <TituloSecao nivel={3}>Previsão contra medição</TituloSecao>
          <p className="mt-3 max-w-3xl text-sm text-texto-suave">
            Toda ordem de correção sai com uma previsão numérica de queda mensal,
            e o FAROL volta em 30 dias para conferir. A hipótese que erra fica
            publicada: uma taxa de acerto que nunca mostra erro não mede nada.
          </p>
          <div className="mt-4">
            <Legenda
              itens={[
                { rotulo: 'Previsto', cor: 'var(--serie-1)' },
                { rotulo: 'Medido', cor: 'var(--serie-2)' },
              ]}
            />
          </div>
          <div className="mt-5">
            <BarrasComparadas
              itens={s.ordens_medidas.map((o) => ({
                rotulo: o.acao,
                previsto: o.previsto,
                medido: o.medido,
                acertou: o.acertou,
              }))}
            />
          </div>
        </section>
      )}

      {/* Para onde a triagem mandou cada caso. */}
      {s && s.destino_dos_casos.length > 0 && (
        <section className="rounded-[--radius-card] border border-borda bg-superficie p-6">
          <TituloSecao nivel={3}>Destino dos casos</TituloSecao>
          <p className="mt-3 max-w-3xl text-sm text-texto-suave">
            A decisão de escalar não é tomada por IA: é a tabela determinística
            publicada em “Como o FAROL decide”. Esta é a distribuição que ela
            produziu.
          </p>
          <div className="mt-4">
            <BarraEmpilhada
              partes={['responde', 'responde_com_oferta_humana', 'escala'].map(
                (chave, i) => ({
                  rotulo: NOME_DA_DECISAO[chave] ?? chave,
                  valor:
                    s.destino_dos_casos.find((x) => x.decisao === chave)?.total ?? 0,
                  cor: corDaSerie(i),
                }),
              )}
            />
          </div>
        </section>
      )}

      <section>
        <TituloSecao nivel={3}>Qualidade do atendimento</TituloSecao>
        <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Pequeno rotulo="Antecipação efetiva" valor={pct(d.taxa_antecipacao_efetiva)} />
          <Pequeno rotulo="Resolução sem humano" valor={pct(d.taxa_resolucao_sem_humano)} />
          <Pequeno
            rotulo="Confirmação de resolução"
            valor={pct(d.taxa_confirmacao_resolucao)}
          />
          <Pequeno rotulo="Acerto das previsões" valor={pct(d.acerto_das_previsoes)} />
        </dl>
      </section>

      <section>
        <TituloSecao nivel={3}>Segurança</TituloSecao>
        <dl className="mt-4 grid gap-3 sm:grid-cols-3">
          <Pequeno
            rotulo="Respostas sem fonte"
            valor={String(d.respostas_sem_fonte)}
            alerta={d.respostas_sem_fonte > 0}
            nota="meta: zero"
          />
          <Pequeno rotulo="Casos na fila" valor={String(d.na_fila)} />
          <Pequeno rotulo="Total de casos" valor={String(d.total_de_casos)} />
        </dl>
      </section>

      {/* Todo gráfico tem uma leitura em texto: quem usa leitor de tela, ou
          precisa do número exato, não fica dependendo do hover. */}
      {s && (
        <section>
          <button
            type="button"
            onClick={() => setTabela((v) => !v)}
            className="text-sm font-semibold text-azul underline underline-offset-4"
          >
            {tabela ? 'Ocultar' : 'Ver'} os números em tabela
          </button>
          {tabela && (
            <div className="mt-3 overflow-x-auto rounded-[--radius-card] border border-borda">
              <table className="w-full text-sm">
                <caption className="sr-only">
                  Volume semanal de atendimentos, por semana
                </caption>
                <thead className="bg-superficie-alt text-left">
                  <tr>
                    <th className="px-3 py-2 font-semibold">Semana</th>
                    <th className="px-3 py-2 font-semibold">Chegaram</th>
                    <th className="px-3 py-2 font-semibold">Evitados</th>
                    <th className="px-3 py-2 font-semibold">Sem humano</th>
                    <th className="px-3 py-2 font-semibold">Escalados</th>
                  </tr>
                </thead>
                <tbody>
                  {s.semanas.map((semana, i) => (
                    <tr key={semana} className="border-t border-borda">
                      <td className="px-3 py-2">{semana}</td>
                      <td className="px-3 py-2">{s.volume.chegaram[i]}</td>
                      <td className="px-3 py-2">{s.volume.evitados[i]}</td>
                      <td className="px-3 py-2">
                        {s.volume.resolvidos_sem_humano[i]}
                      </td>
                      <td className="px-3 py-2">{s.volume.escalados[i]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      <p className="text-sm text-texto-suave">
        Um traço significa que ainda não há amostra suficiente. O painel não
        inventa número para preencher espaço: todo valor desta tela é calculado
        por consulta sobre as tabelas de operação.
      </p>
    </div>
  )
}

function Grande({
  rotulo,
  valor,
  nota,
  serie,
  cor,
  selos,
}: {
  rotulo: string
  valor: string
  nota: string
  serie?: number[]
  cor?: string
  selos?: boolean[]
}) {
  return (
    <div className="flex flex-col rounded-[--radius-card] border border-borda bg-superficie p-6">
      <p className="text-sm font-semibold text-texto-suave">{rotulo}</p>
      <p className="mt-2 text-5xl font-bold text-azul-titulo">{valor}</p>
      <div className="mt-3 h-0.5 w-12 bg-ciano" aria-hidden />
      <p className="mt-3 text-xs text-texto-suave">{nota}</p>
      {/* A faísca dá direção ao número. Sem ela, "279" não diz se está
          subindo ou descendo, que é a única coisa que esta tela promete. */}
      {serie && cor && (
        <div className="mt-auto pt-4">
          <Sparkline valores={serie} cor={cor} maximo={Math.max(...serie)} altura={40} />
        </div>
      )}

      {selos && selos.length > 0 && (
        <div className="mt-auto flex items-center gap-2 pt-4">
          <div className="flex gap-1.5" aria-hidden>
            {selos.map((acertou, i) => (
              <span
                key={i}
                className={[
                  'h-2 w-6 rounded-full',
                  acertou ? 'bg-sucesso' : 'bg-alerta/40',
                ].join(' ')}
              />
            ))}
          </div>
          <span className="text-xs text-texto-suave">
            de {selos.length} ordens medidas
          </span>
        </div>
      )}
    </div>
  )
}

function Pequeno({
  rotulo,
  valor,
  nota,
  alerta,
}: {
  rotulo: string
  valor: string
  nota?: string
  alerta?: boolean
}) {
  return (
    <div
      className={[
        'rounded-[--radius-card] border p-4',
        alerta ? 'border-alerta bg-alerta/5' : 'border-borda bg-superficie',
      ].join(' ')}
    >
      <dt className="text-xs text-texto-suave">{rotulo}</dt>
      <dd
        className={[
          'mt-1 text-3xl font-bold',
          alerta ? 'text-alerta' : 'text-azul-titulo',
        ].join(' ')}
      >
        {valor}
      </dd>
      {nota && <p className="mt-1 text-xs text-texto-suave">{nota}</p>}
    </div>
  )
}
