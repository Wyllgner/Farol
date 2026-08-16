import { useEffect, useState } from 'react'
import { CabecalhoConteudo, TituloSecao } from './componentes/Ui'

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

  if (!d) return <p className="text-texto-suave">Carregando indicadores…</p>

  return (
    <div className="space-y-8">
      <CabecalhoConteudo
        chapeu="Gestão · Métrica invertida"
        titulo="Sucesso, aqui, é este painel diminuir"
        descricao="Todo painel de chatbot comemora quando o número de conversas sobe. O do FAROL comemora quando desce — porque significa que as causas estão sendo eliminadas."
      />

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

      <p className="text-sm text-texto-suave">
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
    <div className="rounded-[--radius-card] border border-borda bg-superficie p-6">
      <p className="text-sm font-semibold text-texto-suave">{rotulo}</p>
      <p className="mt-2 text-5xl font-bold text-azul-titulo">{valor}</p>
      <div className="mt-3 h-0.5 w-12 bg-ciano" aria-hidden />
      <p className="mt-3 text-xs text-texto-suave">{nota}</p>
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
