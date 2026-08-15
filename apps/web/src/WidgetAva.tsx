import { useEffect, useRef, useState } from 'react'
import { agora, comNegrito, type Balao } from './tipos'

type Props = {
  handle: string
  /** O widget sabe em que página do AVA a pessoa está. */
  pagina: string
}

export default function WidgetAva({ handle, pagina }: Props) {
  const [aberto, setAberto] = useState(false)
  const [baloes, setBaloes] = useState<Balao[]>([])
  const [acoes, setAcoes] = useState<string[]>([])
  const [rascunho, setRascunho] = useState('')
  const [carregando, setCarregando] = useState(false)
  const fim = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fim.current?.scrollIntoView({ behavior: 'smooth' })
  }, [baloes, carregando])

  async function enviar(texto: string) {
    const conteudo = texto.trim()
    if (!conteudo || carregando) return

    setBaloes((a) => [
      ...a,
      { id: crypto.randomUUID(), direcao: 'entrada', texto: conteudo, hora: agora() },
    ])
    setAcoes([])
    setRascunho('')
    setCarregando(true)

    try {
      const resposta = await fetch('/api/widget/mensagem', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ handle, texto: conteudo, pagina }),
      })
      if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`)
      const dado = await resposta.json()

      setAcoes(dado.acoes_rapidas)
      setBaloes((a) => [
        ...a,
        {
          id: crypto.randomUUID(),
          direcao: 'saida',
          texto: dado.texto,
          fontes: dado.fontes,
          hora: agora(),
        },
      ])
    } catch {
      setBaloes((a) => [
        ...a,
        {
          id: crypto.randomUUID(),
          direcao: 'saida',
          texto: 'Não consegui responder agora. Pode tentar de novo?',
          hora: agora(),
        },
      ])
    } finally {
      setCarregando(false)
    }
  }

  if (!aberto) {
    return (
      <button
        onClick={() => setAberto(true)}
        className="fixed bottom-6 right-6 flex items-center gap-2 rounded-full bg-marinho-700 px-5 text-white shadow-lg"
      >
        <span aria-hidden>💬</span> Precisa de ajuda?
      </button>
    )
  }

  return (
    <section
      className="fixed bottom-6 right-6 flex w-[22rem] flex-col overflow-hidden rounded-[--radius-suave] border border-neutro-300 bg-white shadow-2xl"
      aria-label="Assistente da Escola"
    >
      <header className="flex items-center justify-between bg-marinho-700 px-4 py-3 text-white">
        <div className="min-w-0">
          <p className="font-semibold">FAROL</p>
          <p className="truncate text-xs text-white/75">{pagina}</p>
        </div>
        <button
          onClick={() => setAberto(false)}
          className="text-2xl leading-none"
          aria-label="Fechar assistente"
        >
          ×
        </button>
      </header>

      <div
        className="h-80 space-y-3 overflow-y-auto bg-neutro-50 px-3 py-4"
        role="log"
        aria-live="polite"
      >
        {baloes.length === 0 && (
          <p className="text-sm text-neutro-600">
            Vi que você está em <strong>{pagina}</strong>. Como posso ajudar?
          </p>
        )}

        {baloes.map((b) => (
          <div
            key={b.id}
            className={b.direcao === 'entrada' ? 'flex justify-end' : 'flex justify-start'}
          >
            <div
              className={[
                'max-w-[85%] rounded-[--radius-suave] px-3 py-2 text-base',
                b.direcao === 'entrada'
                  ? 'bg-marinho-700 text-white'
                  : 'border border-neutro-300 bg-white text-neutro-900',
              ].join(' ')}
            >
              <p
                className="whitespace-pre-wrap break-words"
                dangerouslySetInnerHTML={{ __html: comNegrito(b.texto) }}
              />
              {b.fontes && b.fontes.length > 0 && (
                <p className="mt-2 border-t border-neutro-100 pt-1 text-xs opacity-75">
                  Fonte: {b.fontes.map((f) => f.documento).join(' · ')}
                </p>
              )}
            </div>
          </div>
        ))}

        {carregando && <p className="text-sm text-neutro-600">Consultando…</p>}
        <div ref={fim} />
      </div>

      {acoes.length > 0 && (
        <div className="flex flex-wrap gap-2 border-t border-neutro-100 bg-white px-3 py-2">
          {acoes.map((acao) => (
            <button
              key={acao}
              onClick={() => enviar(acao)}
              className="rounded-full border border-marinho-500 px-3 text-sm text-marinho-700"
            >
              {acao}
            </button>
          ))}
        </div>
      )}

      <form
        className="flex gap-2 border-t border-neutro-300 p-2"
        onSubmit={(e) => {
          e.preventDefault()
          enviar(rascunho)
        }}
      >
        <label htmlFor="widget-msg" className="sr-only">
          Mensagem
        </label>
        <input
          id="widget-msg"
          value={rascunho}
          onChange={(e) => setRascunho(e.target.value)}
          placeholder="Escreva sua dúvida"
          className="min-h-[44px] flex-1 rounded-[--radius-suave] border border-neutro-300 px-3 text-base"
        />
        <button
          type="submit"
          disabled={!rascunho.trim() || carregando}
          className="rounded-[--radius-suave] bg-marinho-700 px-4 text-white disabled:opacity-40"
        >
          Enviar
        </button>
      </form>
    </section>
  )
}
