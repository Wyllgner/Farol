import { useCallback, useEffect, useState } from 'react'
import { apiRestrita, jsonRestrito } from './api'
import { CabecalhoConteudo, Cartao, Etiqueta, TituloSecao } from './componentes/Ui'

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
      jsonRestrito<Politica>('/api/como-decide'),
      jsonRestrito<Ensaio>('/api/ensaio'),
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
      await apiRestrita(`/api/ensaio/${categoria}/${liberar ? 'liberar' : 'recolher'}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ servidor: SERVIDOR }),
      })
      await carregar()
    } finally {
      setOcupado(false)
    }
  }

  if (!p || !e) return <p className="text-texto-suave">Carregando…</p>

  return (
    <div className="space-y-8">
      <CabecalhoConteudo
        chapeu="Gestão · Transparência"
        titulo="Como o FAROL decide"
        descricao="A mesma tabela que o código executa é a que aparece aqui. O sistema não é caixa-preta nem para o servidor nem para o gestor."
      />

      <section>
        <TituloSecao nivel={3}>Política de triagem</TituloSecao>
        <p className="mt-2 text-sm text-texto-suave">
          Determinística e auditável. Não é a IA que decide quando escalar.
        </p>
        <div className="mt-3 overflow-x-auto rounded-[--radius-card] border border-borda">
          <table className="w-full min-w-[42rem] border-collapse text-sm">
            <thead>
              <tr className="bg-azul text-left text-sobre-azul">
                <th className="px-4 py-2.5 font-semibold">Situação</th>
                <th className="px-4 py-2.5 font-semibold">Critério</th>
                <th className="px-4 py-2.5 font-semibold">Ação</th>
              </tr>
            </thead>
            <tbody>
              {p.politica_de_triagem.map((r, i) => (
                <tr
                  key={r.situacao}
                  className={i % 2 === 1 ? 'bg-superficie-alt' : 'bg-superficie'}
                >
                  <td className="px-4 py-2.5 text-texto">{r.situacao}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-texto-suave">
                    {r.criterio}
                  </td>
                  <td className="px-4 py-2.5 font-medium text-azul-titulo">{r.acao}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <blockquote className="mt-4 rounded-[--radius-controle] border-l-4 border-ciano bg-superficie-alt p-4 text-sm italic">
          {p.texto_da_recusa}
        </blockquote>
      </section>

      {/* Modo Ensaio: a liberação é humana, explícita e reversível. */}
      <section>
        <TituloSecao nivel={3}>
          Modo Ensaio {e.modo_ensaio_ativo ? '· ligado' : '· desligado'}
        </TituloSecao>
        <p className="mt-2 max-w-3xl text-sm text-texto-suave">
          Com o ensaio ligado, o FAROL gera a resposta mas não envia: o servidor
          confere e aprova. Uma categoria só passa a responder sozinha depois de{' '}
          <strong className="text-texto">
            {Math.round(e.taxa_para_liberar * 100)}% de acerto
          </strong>{' '}
          em ao menos {e.amostra_minima} revisões. Não pedimos confiança: 
          pedimos observação.
        </p>

        <ul className="mt-4 grid gap-2 sm:grid-cols-2">
          {e.categorias.map((c) => (
            <li
              key={c.categoria}
              className="flex items-center justify-between gap-3 rounded-[--radius-card] border border-borda bg-superficie p-3"
            >
              <div className="min-w-0">
                <p className="truncate font-medium text-texto">{c.categoria}</p>
                <p className="text-xs text-texto-suave">
                  {c.revisados === 0
                    ? 'sem revisões'
                    : `${c.aprovados}/${c.revisados} aprovados · ${Math.round((c.taxa_acerto ?? 0) * 100)}%`}
                </p>
              </div>
              <button
                disabled={ocupado}
                onClick={() => alternar(c.categoria, !c.liberada)}
                aria-pressed={c.liberada}
                className={[
                  'shrink-0 rounded-full px-3 text-xs font-semibold transition-colors',
                  c.liberada
                    ? 'bg-azul text-sobre-azul hover:bg-azul-escuro'
                    : 'border border-borda text-texto-suave hover:bg-superficie-alt',
                ].join(' ')}
              >
                {c.liberada ? 'liberada' : 'em ensaio'}
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <TituloSecao nivel={3}>Gatilhos proativos</TituloSecao>
        <ul className="mt-4 space-y-2">
          {p.gatilhos.map((g) => (
            <li
              key={g.chave}
              className="flex items-start justify-between gap-3 rounded-[--radius-card] border border-borda bg-superficie p-3 text-sm"
            >
              <div className="min-w-0">
                <p className="text-texto">{g.titulo}</p>
                <p className="text-xs text-texto-suave">{g.motivo}</p>
              </div>
              <Etiqueta tom={g.ativo ? 'proativo' : 'alerta'}>
                {g.ativo ? 'ativo' : 'desativado'}
              </Etiqueta>
            </li>
          ))}
        </ul>
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <Caixa titulo="Regras do grafo" dados={p.regras_do_grafo} />
        <Caixa titulo="Base de conhecimento" dados={p.conhecimento} />
      </section>

      <p className="text-sm text-texto-suave">
        Classificação: <code className="text-azul-titulo">{p.modelo.classificacao}</code>{' '}
        · Geração: <code className="text-azul-titulo">{p.modelo.geracao}</code>
      </p>
    </div>
  )
}

function Caixa({ titulo, dados }: { titulo: string; dados: Record<string, number> }) {
  return (
    <Cartao>
      <h4 className="text-sm font-bold tracking-wider uppercase">{titulo}</h4>
      <div className="mt-2 h-0.5 w-10 bg-ciano" aria-hidden />
      <dl className="mt-3 space-y-1.5 text-sm">
        {Object.entries(dados).map(([chave, valor]) => (
          <div key={chave} className="flex justify-between gap-4">
            <dt className="text-texto-suave">{chave.replaceAll('_', ' ')}</dt>
            <dd className="font-semibold text-azul-titulo">{valor}</dd>
          </div>
        ))}
      </dl>
    </Cartao>
  )
}
