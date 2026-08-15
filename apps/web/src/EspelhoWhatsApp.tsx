import { useCallback, useEffect, useRef, useState } from 'react'
import { agora, comNegrito, type Balao, type EventoServidor } from './tipos'

type Props = {
  /** Telefone do participante. Vazio = anônimo, e o produto segue útil. */
  handle: string
}

export default function EspelhoWhatsApp({ handle }: Props) {
  const [baloes, setBaloes] = useState<Balao[]>([])
  const [acoes, setAcoes] = useState<string[]>([])
  const [digitando, setDigitando] = useState(false)
  const [conectado, setConectado] = useState(false)
  const [rascunho, setRascunho] = useState('')

  const socket = useRef<WebSocket | null>(null)
  const fim = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const ws = new WebSocket(
      `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/ws/espelho/${encodeURIComponent(handle || 'anonimo')}`,
    )
    socket.current = ws

    ws.onopen = () => setConectado(true)
    ws.onclose = () => setConectado(false)
    ws.onmessage = (evento) => {
      const dado: EventoServidor = JSON.parse(evento.data)
      if (dado.tipo === 'digitando') {
        setDigitando(true)
        return
      }
      setDigitando(false)
      setAcoes(dado.acoes_rapidas)
      setBaloes((atuais) => [
        ...atuais,
        {
          id: crypto.randomUUID(),
          direcao: 'saida',
          texto: dado.texto,
          fontes: dado.fontes,
          hora: agora(),
        },
      ])
    }

    return () => ws.close()
  }, [handle])

  useEffect(() => {
    fim.current?.scrollIntoView({ behavior: 'smooth' })
  }, [baloes, digitando])

  const enviar = useCallback(
    (texto: string) => {
      const conteudo = texto.trim()
      if (!conteudo || socket.current?.readyState !== WebSocket.OPEN) return

      setBaloes((atuais) => [
        ...atuais,
        {
          id: crypto.randomUUID(),
          direcao: 'entrada',
          texto: conteudo,
          hora: agora(),
          entregue: true,
        },
      ])
      setAcoes([])
      setRascunho('')
      socket.current.send(JSON.stringify({ texto: conteudo }))
    },
    [],
  )

  return (
    <div className="mx-auto w-full max-w-[420px]">
      {/* Moldura de celular. O verde vive só aqui, por fidelidade. */}
      <div className="overflow-hidden rounded-[2rem] border-8 border-neutro-900 bg-zap-fundo shadow-2xl">
        <header className="flex items-center gap-3 bg-zap-barra px-4 py-3 text-white">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-white/20 text-sm font-semibold">
            FA
          </div>
          <div className="min-w-0">
            <p className="truncate font-semibold">EMERON · SECOEAD</p>
            <p className="text-xs text-white/80">
              {conectado ? (digitando ? 'digitando…' : 'online') : 'conectando…'}
            </p>
          </div>
        </header>

        <div
          className="h-[30rem] space-y-2 overflow-y-auto px-3 py-4"
          role="log"
          aria-live="polite"
          aria-label="Conversa"
        >
          {baloes.length === 0 && (
            <p className="mx-auto mt-8 max-w-[80%] rounded-lg bg-white/70 px-3 py-2 text-center text-sm text-neutro-600">
              Mande uma mensagem para a Escola. Pergunte como se estivesse
              falando com uma pessoa.
            </p>
          )}

          {baloes.map((balao) => (
            <BalaoMensagem key={balao.id} balao={balao} />
          ))}

          {digitando && (
            <div className="w-fit rounded-lg rounded-tl-none bg-white px-3 py-2 shadow-sm">
              <span className="sr-only">Digitando</span>
              <span className="flex gap-1" aria-hidden>
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="h-2 w-2 animate-bounce rounded-full bg-neutro-300"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </span>
            </div>
          )}
          <div ref={fim} />
        </div>

        {acoes.length > 0 && (
          <div className="flex flex-wrap gap-2 bg-zap-fundo px-3 pb-2">
            {acoes.map((acao) => (
              <button
                key={acao}
                onClick={() => enviar(acao)}
                className="rounded-full border border-zap-barra/30 bg-white px-4 text-sm font-medium text-zap-barra"
              >
                {acao}
              </button>
            ))}
          </div>
        )}

        <form
          className="flex items-center gap-2 bg-neutro-100 px-3 py-2"
          onSubmit={(e) => {
            e.preventDefault()
            enviar(rascunho)
          }}
        >
          <label htmlFor="mensagem" className="sr-only">
            Mensagem
          </label>
          <input
            id="mensagem"
            value={rascunho}
            onChange={(e) => setRascunho(e.target.value)}
            placeholder="Mensagem"
            autoComplete="off"
            className="min-h-[44px] flex-1 rounded-full bg-white px-4 text-base outline-none"
          />
          <button
            type="submit"
            disabled={!rascunho.trim()}
            className="grid h-11 w-11 place-items-center rounded-full bg-zap-barra text-white disabled:opacity-40"
            aria-label="Enviar"
          >
            ➤
          </button>
        </form>
      </div>
    </div>
  )
}

function BalaoMensagem({ balao }: { balao: Balao }) {
  const enviada = balao.direcao === 'entrada'
  return (
    <div className={enviada ? 'flex justify-end' : 'flex justify-start'}>
      <div
        className={[
          'max-w-[85%] rounded-lg px-3 py-2 text-base shadow-sm',
          enviada ? 'rounded-tr-none bg-zap-balao' : 'rounded-tl-none bg-white',
        ].join(' ')}
      >
        <p
          className="whitespace-pre-wrap break-words text-neutro-900"
          dangerouslySetInnerHTML={{ __html: comNegrito(balao.texto) }}
        />

        {balao.fontes && balao.fontes.length > 0 && (
          <p className="mt-2 border-t border-neutro-100 pt-1 text-xs text-neutro-600">
            Fonte: {balao.fontes.map((f) => f.documento).join(' · ')}
          </p>
        )}

        <p className="mt-1 flex items-center justify-end gap-1 text-[0.6875rem] text-neutro-600">
          {balao.hora}
          {enviada && <span aria-label="Entregue">✓✓</span>}
        </p>
      </div>
    </div>
  )
}
