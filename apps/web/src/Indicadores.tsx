import { useEffect, useState } from 'react'

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

function pct(v: number | null): string {
  return v === null ? '—' : `${Math.round(v * 100)}%`
}

export default function Indicadores() {
  const [d, setDados] = useState<Dados | null>(null)

  useEffect(() => {
    fetch('/api/indicadores')
      .then((r) => r.json())
      .then(setDados)
      .catch(() => setDados(null))
  }, [])

  if (!d) return <p className="text-neutro-600">Carregando indicadores…</p>

  return (
    <div className="space-y-10">
      <header>
        <p className="text-xs font-medium tracking-widest text-dourado-600 uppercase">
          Indicadores
        </p>
        <h2 className="text-2xl font-semibold text-marinho-900">
          Sucesso, aqui, é este painel diminuir
        </h2>
        <p className="mt-1 max-w-2xl text-sm text-neutro-600">
          Todo painel de chatbot comemora quando o número de conversas sobe. O
          do FAROL comemora quando desce — porque significa que as causas estão
          sendo eliminadas.
        </p>
      </header>

      {/* A métrica invertida vem primeiro, grande, sozinha. */}
      <section className="grid gap-4 sm:grid-cols-3">
        <Grande
          rotulo="Atendimentos evitados"
          valor={String(d.atendimentos_evitados)}
          nota="comprovados por hipótese verificada"
        />
        <Grande
          rotulo="Horas devolvidas à equipe"
          valor={`${d.horas_devolvidas_a_equipe}h`}
          nota="tempo que voltou para o trabalho estratégico"
        />
        <Grande
          rotulo="Causas extintas"
          valor={String(d.causas_extintas)}
          nota="correções com queda confirmada"
        />
      </section>

      <section>
        <h3 className="text-sm font-semibold tracking-wide text-neutro-600 uppercase">
          Qualidade do atendimento
        </h3>
        <dl className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Pequeno rotulo="Antecipação efetiva" valor={pct(d.taxa_antecipacao_efetiva)} />
          <Pequeno rotulo="Resolução sem humano" valor={pct(d.taxa_resolucao_sem_humano)} />
          <Pequeno rotulo="Confirmação de resolução" valor={pct(d.taxa_confirmacao_resolucao)} />
          <Pequeno rotulo="Acerto das previsões" valor={pct(d.acerto_das_previsoes)} />
        </dl>
      </section>

      <section>
        <h3 className="text-sm font-semibold tracking-wide text-neutro-600 uppercase">
          Segurança
        </h3>
        <dl className="mt-3 grid gap-3 sm:grid-cols-3">
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

      <p className="text-sm text-neutro-600">
        Um traço significa que ainda não há amostra suficiente. O painel não
        inventa número para preencher espaço.
      </p>
    </div>
  )
}

function Grande({
  rotulo,
  valor,
  nota,
}: {
  rotulo: string
  valor: string
  nota: string
}) {
  return (
    <div className="rounded-[--radius-suave] border-2 border-marinho-500 bg-white p-6">
      <p className="text-sm font-medium text-neutro-600">{rotulo}</p>
      <p className="mt-2 text-5xl font-semibold text-marinho-900">{valor}</p>
      <p className="mt-2 text-xs text-neutro-600">{nota}</p>
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
        'rounded-[--radius-suave] border bg-white p-4',
        alerta ? 'border-dourado-600' : 'border-neutro-300',
      ].join(' ')}
    >
      <dt className="text-xs text-neutro-600">{rotulo}</dt>
      <dd
        className={[
          'mt-1 text-3xl font-semibold',
          alerta ? 'text-dourado-600' : 'text-marinho-900',
        ].join(' ')}
      >
        {valor}
      </dd>
      {nota && <p className="mt-1 text-xs text-neutro-600">{nota}</p>}
    </div>
  )
}
