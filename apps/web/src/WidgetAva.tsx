import { useEffect, useRef, useState } from 'react'
import {
  IconeConversa,
  IconeEnviar,
  IconeFarol,
  IconeFechar,
  IconeFonte,
} from './componentes/Icones'
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
        className="fixed right-4 bottom-4 z-40 flex items-center gap-2 rounded-full bg-azul px-5 text-sobre-azul shadow-lg transition-colors hover:bg-azul-escuro sm:right-6 sm:bottom-6"
      >
        <IconeConversa className="h-5 w-5" />
        <span className="text-sm font-semibold">Precisa de ajuda?</span>
      </button>
    )
  }

  return (
    <section
      /* No celular ocupa a tela inteira; no desktop é uma janela flutuante. */
      className="fixed inset-0 z-40 flex flex-col bg-superficie sm:inset-auto sm:right-6 sm:bottom-6 sm:h-[34rem] sm:w-[23rem] sm:rounded-[--radius-card] sm:border sm:border-borda sm:shadow-2xl"
      aria-label="Assistente da Escola"
    >
      <header className="flex items-center justify-between gap-3 bg-azul px-4 py-3 text-sobre-azul sm:rounded-t-[--radius-card]">
        <div className="flex min-w-0 items-center gap-2">
          <IconeFarol className="h-6 w-6 shrink-0" />
          <div className="min-w-0">
            <p className="font-bold tracking-wide uppercase">Farol</p>
            <p className="truncate text-xs text-sobre-azul/80">{pagina}</p>
          </div>
        </div>
        <button
          onClick={() => setAberto(false)}
          className="shrink-0 text-sobre-azul"
          aria-label="Fechar assistente"
        >
          <IconeFechar className="h-5 w-5" />
        </button>
      </header>
      <div className="h-0.5 bg-ciano" aria-hidden />

      <div
        className="flex-1 space-y-3 overflow-y-auto bg-superficie-alt px-3 py-4"
        role="log"
        aria-live="polite"
      >
        {baloes.length === 0 && (
          <p className="rounded-[--radius-card] border border-borda bg-superficie p-3 text-sm text-texto-suave">
            Vi que você está em <strong className="text-azul-titulo">{pagina}</strong>.
            Como posso ajudar?
          </p>
        )}

        {baloes.map((b) => (
          <div
            key={b.id}
            className={b.direcao === 'entrada' ? 'flex justify-end' : 'flex justify-start'}
          >
            <div
              className={[
                'max-w-[85%] rounded-[--radius-card] px-3 py-2 text-base',
                b.direcao === 'entrada'
                  ? 'rounded-tr-sm bg-azul text-sobre-azul'
                  : 'rounded-tl-sm border border-borda bg-superficie text-texto',
              ].join(' ')}
            >
              <p
                className="break-words whitespace-pre-wrap"
                dangerouslySetInnerHTML={{ __html: comNegrito(b.texto) }}
              />
              {b.fontes && b.fontes.length > 0 && (
                <p className="mt-2 flex items-start gap-1.5 border-t border-borda pt-1.5 text-xs text-texto-suave">
                  <IconeFonte className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>{b.fontes.map((f) => f.documento).join(' · ')}</span>
                </p>
              )}
            </div>
          </div>
        ))}

        {carregando && (
          <p className="text-sm text-texto-suave">
            <span className="sr-only">Consultando a base oficial</span>
            <span aria-hidden>Consultando…</span>
          </p>
        )}
        <div ref={fim} />
      </div>

      {acoes.length > 0 && (
        <div className="flex flex-wrap gap-2 border-t border-borda bg-superficie px-3 py-2">
          {acoes.map((acao) => (
            <button
              key={acao}
              onClick={() => enviar(acao)}
              className="rounded-full border border-azul px-3 text-sm font-semibold text-azul-titulo hover:bg-azul-100"
            >
              {acao}
            </button>
          ))}
        </div>
      )}

      <form
        className="flex gap-2 border-t border-borda bg-superficie p-2 sm:rounded-b-[--radius-card]"
        onSubmit={(e) => {
          e.preventDefault()
          enviar(rascunho)
        }}
      >
        <label htmlFor="widget-msg" className="sr-only">
          Escreva sua dúvida
        </label>
        <input
          id="widget-msg"
          value={rascunho}
          onChange={(e) => setRascunho(e.target.value)}
          placeholder="Escreva sua dúvida"
          className="flex-1 rounded-[--radius-controle] border border-borda bg-superficie-alt px-3 text-base text-texto placeholder:text-texto-suave"
        />
        <button
          type="submit"
          disabled={!rascunho.trim() || carregando}
          className="grid h-11 w-11 shrink-0 place-items-center rounded-[--radius-controle] bg-azul text-sobre-azul hover:bg-azul-escuro disabled:opacity-40"
          aria-label="Enviar"
        >
          <IconeEnviar className="h-5 w-5" />
        </button>
      </form>
    </section>
  )
}
