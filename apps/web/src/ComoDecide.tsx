import { useCallback, useEffect, useState } from 'react'

type Regra = { situacao: string; criterio: string; acao: string }

type Gatilho = {
  chave: string
  titulo: string
  ativo: boolean
  motivo: string
  antecipacao_efetiva: number | null
}

type Politica = {
  politica_de_triagem: Regra[]
  texto_da_recusa: string
  gatilhos: Gatilho[]
  regras_do_grafo: Record<string, number>
  conhecimento: Record<string, number>
  modelo: { classificacao: string; geracao: string; modo_ensaio: boolean }
}

type CategoriaEnsaio = {
  categoria: string
  revisados: number
  aprovados: number
  taxa_acerto: number | null
  liberada: boolean
  pode_liberar: boolean
}

type Ensaio = {
  modo_ensaio_ativo: boolean
  taxa_para_liberar: number
  amostra_minima: number
  categorias: CategoriaEnsaio[]
}

const SERVIDOR = 'Servidora Ana (SECOEAD)'

export default function ComoDecide() {
  const [p, setPolitica] = useState<Politica | null>(null)
  const [e, setEnsaio] = useState<Ensaio | null>(null)
  const [ocupado, setOcupado] = useState(false)

  const carregar = useCallback(async () => {
    const [politica, ensaio] = await Promise.all([
      fetch('/api/como-decide').then((r) => r.json()),
      fetch('/api/ensaio').then((r) => r.json()),
    ])
    setPolitica(politica)
    setEnsaio(ensaio)
  }, [])

  useEffect(() => {
    carregar()
  }, [carregar])

  async function alternar(categoria: string, liberar: boolean) {
    setOcupado(true)
    try {
      await fetch(
        `/api/ensaio/${categoria}/${liberar ? 'liberar' : 'recolher'}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ servidor: SERVIDOR }),
        },
      )
      await carregar()
    } finally {
      setOcupado(false)
    }
  }

  if (!p || !e) return <p className="text-neutro-600">Carregando…</p>

  return (
    <div className="space-y-10">
      <header>
        <p className="text-xs font-medium tracking-widest text-dourado-600 uppercase">
          Transparência
        </p>
        <h2 className="text-2xl font-semibold text-marinho-900">
          Como o FAROL decide
        </h2>
        <p className="mt-1 max-w-2xl text-sm text-neutro-600">
          A mesma tabela que o código executa é a que aparece aqui. O sistema
          não é caixa-preta nem para o servidor nem para o gestor.
        </p>
      </header>

      <section>
        <h3 className="text-sm font-semibold tracking-wide text-neutro-600 uppercase">
          Política de triagem
        </h3>
        <p className="mt-1 text-sm text-neutro-600">
          Determinística e auditável. Não é a IA que decide quando escalar.
        </p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[40rem] border-collapse text-sm">
            <thead>
              <tr className="border-b border-neutro-300 text-left">
                <th className="py-2 pr-4 font-semibold">Situação</th>
                <th className="py-2 pr-4 font-semibold">Critério</th>
                <th className="py-2 font-semibold">Ação</th>
              </tr>
            </thead>
            <tbody>
              {p.politica_de_triagem.map((r) => (
                <tr key={r.situacao} className="border-b border-neutro-100">
                  <td className="py-2 pr-4 text-neutro-900">{r.situacao}</td>
                  <td className="py-2 pr-4 font-mono text-xs text-neutro-600">
                    {r.criterio}
                  </td>
                  <td className="py-2 text-neutro-900">{r.acao}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <blockquote className="mt-4 border-l-4 border-dourado-400 bg-neutro-50 p-3 text-sm text-neutro-900 italic">
          {p.texto_da_recusa}
        </blockquote>
      </section>

      {/* Modo Ensaio: a liberação é humana, explícita e reversível. */}
      <section>
        <h3 className="text-sm font-semibold tracking-wide text-neutro-600 uppercase">
          Modo Ensaio {e.modo_ensaio_ativo ? '· ligado' : '· desligado'}
        </h3>
        <p className="mt-1 max-w-2xl text-sm text-neutro-600">
          Com o ensaio ligado, o FAROL gera a resposta mas não envia: o
          servidor confere e aprova. Uma categoria só passa a responder
          sozinha depois de{' '}
          <strong>{Math.round(e.taxa_para_liberar * 100)}% de acerto</strong> em
          ao menos {e.amostra_minima} revisões. Não pedimos confiança —
          pedimos observação.
        </p>

        <ul className="mt-3 grid gap-2 sm:grid-cols-2">
          {e.categorias.map((c) => (
            <li
              key={c.categoria}
              className="flex items-center justify-between gap-3 rounded-[--radius-suave] border border-neutro-300 bg-white p-3"
            >
              <div className="min-w-0">
                <p className="truncate text-neutro-900">{c.categoria}</p>
                <p className="text-xs text-neutro-600">
                  {c.revisados === 0
                    ? 'sem revisões'
                    : `${c.aprovados}/${c.revisados} aprovados · ${Math.round((c.taxa_acerto ?? 0) * 100)}%`}
                </p>
              </div>
              <button
                disabled={ocupado}
                onClick={() => alternar(c.categoria, !c.liberada)}
                className={[
                  'shrink-0 rounded-full px-3 text-xs font-medium',
                  c.liberada
                    ? 'bg-marinho-700 text-white'
                    : 'border border-neutro-300 text-neutro-600',
                ].join(' ')}
              >
                {c.liberada ? 'liberada' : 'em ensaio'}
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h3 className="text-sm font-semibold tracking-wide text-neutro-600 uppercase">
          Gatilhos proativos
        </h3>
        <ul className="mt-3 space-y-2">
          {p.gatilhos.map((g) => (
            <li
              key={g.chave}
              className="flex items-start justify-between gap-3 rounded-[--radius-suave] border border-neutro-300 bg-white p-3 text-sm"
            >
              <div>
                <p className="text-neutro-900">{g.titulo}</p>
                <p className="text-xs text-neutro-600">{g.motivo}</p>
              </div>
              <span
                className={[
                  'shrink-0 rounded-full px-2 py-0.5 text-xs',
                  g.ativo
                    ? 'bg-neutro-100 text-neutro-600'
                    : 'bg-dourado-400/20 text-dourado-600',
                ].join(' ')}
              >
                {g.ativo ? 'ativo' : 'desativado'}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <Caixa titulo="Regras do grafo" dados={p.regras_do_grafo} />
        <Caixa titulo="Base de conhecimento" dados={p.conhecimento} />
      </section>

      <p className="text-sm text-neutro-600">
        Classificação: <code>{p.modelo.classificacao}</code> · Geração:{' '}
        <code>{p.modelo.geracao}</code>
      </p>
    </div>
  )
}

function Caixa({
  titulo,
  dados,
}: {
  titulo: string
  dados: Record<string, number>
}) {
  return (
    <div className="rounded-[--radius-suave] border border-neutro-300 bg-white p-4">
      <h4 className="text-sm font-semibold text-neutro-900">{titulo}</h4>
      <dl className="mt-2 space-y-1 text-sm">
        {Object.entries(dados).map(([chave, valor]) => (
          <div key={chave} className="flex justify-between gap-4">
            <dt className="text-neutro-600">{chave.replaceAll('_', ' ')}</dt>
            <dd className="font-medium text-marinho-900">{valor}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
