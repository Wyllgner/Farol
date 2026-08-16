import { useCallback, useEffect, useRef, useState } from 'react'
import { IconeEnviar, IconeFarol, IconeFonte } from './componentes/Icones'
import { AoVivo } from './componentes/Ui'
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

  const enviar = useCallback((texto: string) => {
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
  }, [])

  return (
    <div className="w-full sm:max-w-[26rem]">
      {/* No celular a conversa ocupa a tela; no desktop ganha moldura. */}
      <div className="overflow-hidden bg-superficie sm:rounded-[--radius-card] sm:border sm:border-borda sm:shadow-lg">
        <header className="bg-azul px-4 py-3 text-sobre-azul">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-sobre-azul/15">
              <IconeFarol className="h-6 w-6" />
            </span>
            <div className="min-w-0">
              <p className="truncate font-bold tracking-wide uppercase">
                Farol · SECOEAD
              </p>
              <AoVivo
                ativo={conectado}
                rotulo={
                  conectado
                    ? digitando
                      ? 'digitando…'
                      : 'on-line'
                    : 'conectando…'
                }
              />
            </div>
          </div>
        </header>
        <div className="h-0.5 bg-ciano" aria-hidden />

        <div
          className="h-[60vh] space-y-3 overflow-y-auto bg-superficie-alt px-3 py-4 sm:h-[28rem]"
          role="log"
          aria-live="polite"
          aria-label="Conversa com o FAROL"
        >
          {baloes.length === 0 && (
            <p className="mx-auto mt-8 max-w-[85%] rounded-[--radius-card] border border-borda bg-superficie px-4 py-3 text-center text-sm text-texto-suave">
              Mande uma mensagem para a Escola. Pergunte como se estivesse
              falando com uma pessoa.
            </p>
          )}

          {baloes.map((balao) => (
            <BalaoMensagem key={balao.id} balao={balao} />
          ))}

          {digitando && (
            <div className="w-fit rounded-[--radius-card] rounded-tl-sm border border-borda bg-superficie px-4 py-3">
              <span className="sr-only">O FAROL está digitando</span>
              <span className="flex gap-1" aria-hidden>
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="h-2 w-2 animate-bounce rounded-full bg-ciano"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </span>
            </div>
          )}
          <div ref={fim} />
        </div>

        {acoes.length > 0 && (
          <div className="flex flex-wrap gap-2 border-t border-borda bg-superficie px-3 py-2">
            {acoes.map((acao) => (
              <button
                key={acao}
                onClick={() => enviar(acao)}
                className="rounded-full border border-azul px-4 text-sm font-semibold text-azul-titulo transition-colors hover:bg-azul-100"
              >
                {acao}
              </button>
            ))}
          </div>
        )}

        <form
          className="flex items-center gap-2 border-t border-borda bg-superficie px-3 py-2"
          onSubmit={(e) => {
            e.preventDefault()
            enviar(rascunho)
          }}
        >
          <label htmlFor="mensagem" className="sr-only">
            Escreva sua mensagem
          </label>
          <input
            id="mensagem"
            value={rascunho}
            onChange={(e) => setRascunho(e.target.value)}
            placeholder="Mensagem"
            autoComplete="off"
            className="flex-1 rounded-full border border-borda bg-superficie-alt px-4 text-base text-texto placeholder:text-texto-suave"
          />
          <button
            type="submit"
            disabled={!rascunho.trim()}
            className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-azul text-sobre-azul transition-colors hover:bg-azul-escuro disabled:opacity-40"
            aria-label="Enviar mensagem"
          >
            <IconeEnviar className="h-5 w-5" />
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
          'max-w-[85%] rounded-[--radius-card] px-4 py-2.5 text-base',
          enviada
            ? 'rounded-tr-sm bg-azul-100 text-texto'
            : 'rounded-tl-sm border border-borda bg-superficie text-texto',
        ].join(' ')}
      >
        <p
          className="break-words whitespace-pre-wrap"
          dangerouslySetInnerHTML={{ __html: comNegrito(balao.texto) }}
        />

        {balao.fontes && balao.fontes.length > 0 && (
          <p className="mt-2 flex items-start gap-1.5 border-t border-borda pt-2 text-xs text-texto-suave">
            <IconeFonte className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{balao.fontes.map((f) => f.documento).join(' · ')}</span>
          </p>
        )}

        <p className="mt-1 text-right text-[0.6875rem] text-texto-suave">
          {balao.hora}
          {enviada && <span aria-label=", entregue"> ✓✓</span>}
        </p>
      </div>
    </div>
  )
}
