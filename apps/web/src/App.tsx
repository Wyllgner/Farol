import { useEffect, useState } from 'react'

type Saude = {
  servico: string
  banco: string
  llm: string
  embeddings: string
  canal: string
  modo_ensaio: boolean
}

export default function App() {
  const [saude, setSaude] = useState<Saude | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setSaude)
      .catch((e: Error) => setErro(e.message))
  }, [])

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <p className="text-sm font-medium tracking-widest text-dourado-600 uppercase">
        SECOEAD · EMERON
      </p>
      <h1 className="mt-2 text-4xl font-semibold text-marinho-900">FAROL</h1>
      <p className="mt-3 text-lg text-neutro-600">
        Responde antes da pergunta. E trabalha para nunca mais precisar responder.
      </p>

      <section className="mt-10 rounded-[--radius-suave] border border-neutro-300 bg-white p-6 shadow-sm">
        <h2 className="text-sm font-semibold tracking-wide text-neutro-600 uppercase">
          Estado do sistema
        </h2>

        {erro && (
          <p className="mt-4 text-marinho-700">
            API indisponível ({erro}). Suba com <code>make dev</code>.
          </p>
        )}

        {!saude && !erro && <p className="mt-4 text-neutro-600">Consultando…</p>}

        {saude && (
          <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <Linha rotulo="Banco" valor={saude.banco} />
            <Linha rotulo="Modelo de linguagem" valor={saude.llm} />
            <Linha rotulo="Embeddings" valor={saude.embeddings} />
            <Linha rotulo="Canal" valor={saude.canal} />
            <Linha
              rotulo="Modo Ensaio"
              valor={saude.modo_ensaio ? 'ligado' : 'desligado'}
            />
          </dl>
        )}
      </section>
    </main>
  )
}

function Linha({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <>
      <dt className="text-neutro-600">{rotulo}</dt>
      <dd className="font-medium text-marinho-900">{valor}</dd>
    </>
  )
}
