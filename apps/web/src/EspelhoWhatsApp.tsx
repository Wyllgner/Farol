import { useCallback, useEffect, useRef, useState } from 'react'
import {
  IconeBateria,
  IconeCamera,
  IconeChamada,
  IconeClipe,
  IconeEmoji,
  IconeEnviar,
  IconeFarol,
  IconeMicrofone,
  IconeSinal,
  IconeTiques,
  IconeTresPontos,
  IconeVideo,
  IconeVoltar,
  IconeWifi,
} from './componentes/Icones'
import { agora, comNegrito, type Balao, type EventoServidor } from './tipos'

type Props = {
  /** Telefone do participante. Vazio = anônimo, e o produto segue útil. */
  handle: string
}

/**
 * Espelho do WhatsApp: um celular aberto na conversa com a Escola.
 *
 * A moldura não é enfeite. A promessa do produto é chegar no canal que a
 * pessoa já usa, e uma janela de chat genérica não prova isso a quem
 * assiste: prova um chat. O que convence é reconhecer a tela antes de ler
 * qualquer palavra, e é por isso que aqui há barra de status, papel de
 * parede rabiscado, rabinho de balão e tique azul.
 *
 * A interface é reproduzida, não copiada: as cores vivem em tokens
 * próprios no CSS, os ícones foram redesenhados no traço do projeto e o
 * papel de parede é um SVG nosso. Imitar o comportamento de um canal não
 * autoriza redistribuir o material gráfico da Meta.
 */
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
  }, [baloes.length, digitando, acoes.length])

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

  const temRascunho = rascunho.trim().length > 0

  return (
    <div className="w-full sm:max-w-[24.5rem]">
      {/* Moldura do aparelho. No celular ela some: quem já está num
          celular não precisa da imagem de um. */}
      <div className="zap-aparelho overflow-hidden bg-zap-fundo sm:rounded-[2.75rem] sm:border-[0.55rem] sm:border-zap-moldura">
        <BarraDeStatus />

        <header className="flex items-center gap-3 bg-zap-barra px-2 py-2 text-white">
          <button
            type="button"
            className="grid h-9 w-7 shrink-0 place-items-center opacity-95"
            aria-label="Voltar para as conversas"
          >
            <IconeVoltar className="h-5 w-5" />
          </button>

          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-white/20">
            <IconeFarol className="h-6 w-6" />
          </span>

          <div className="min-w-0 flex-1 leading-tight">
            <p className="truncate text-[0.975rem] font-medium">
              Farol · SECOEAD
            </p>
            <p className="truncate text-[0.75rem] text-white/85">
              {conectado ? (digitando ? 'digitando…' : 'online') : 'conectando…'}
            </p>
          </div>

          <div className="flex items-center gap-1 pr-1 text-white/95">
            <button
              type="button"
              className="grid h-9 w-8 place-items-center"
              aria-label="Chamada de vídeo"
            >
              <IconeVideo className="h-5 w-5" />
            </button>
            <button
              type="button"
              className="grid h-9 w-8 place-items-center"
              aria-label="Chamada de voz"
            >
              <IconeChamada className="h-5 w-5" />
            </button>
            <button
              type="button"
              className="grid h-9 w-6 place-items-center"
              aria-label="Mais opções"
            >
              <IconeTresPontos className="h-5 w-5" />
            </button>
          </div>
        </header>

        <div
          className="zap-papel h-[62vh] space-y-2 overflow-y-auto px-3 py-3 sm:h-[27rem]"
          role="log"
          aria-live="polite"
          aria-label="Conversa com o FAROL"
        >
          <Etiqueta className="bg-white/95 text-zap-hora">HOJE</Etiqueta>
          <Etiqueta className="bg-zap-aviso text-zap-aviso-texto">
            As mensagens são atendidas pela SECOEAD. Dados fictícios de
            demonstração.
          </Etiqueta>

          {baloes.map((balao) => (
            <BalaoMensagem key={balao.id} balao={balao} />
          ))}

          {digitando && (
            <div className="flex justify-start">
              <div className="zap-rabo-recebida relative ml-2 rounded-lg rounded-tl-none bg-zap-recebida px-4 py-3 shadow-sm">
                <span className="sr-only">O FAROL está digitando</span>
                <span className="flex gap-1" aria-hidden>
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      className="h-2 w-2 animate-bounce rounded-full bg-zap-hora/60"
                      style={{ animationDelay: `${i * 0.15}s` }}
                    />
                  ))}
                </span>
              </div>
            </div>
          )}

          {/* Botões de resposta rápida: no WhatsApp eles nascem colados no
              balão que os ofereceu, e não numa barra separada. */}
          {acoes.length > 0 && !digitando && (
            <div className="ml-2 max-w-[85%] space-y-px overflow-hidden rounded-b-lg">
              {acoes.map((acao) => (
                <button
                  key={acao}
                  onClick={() => enviar(acao)}
                  className="block w-full bg-zap-recebida py-2.5 text-center text-[0.9rem] font-medium text-zap-acao shadow-sm transition-colors hover:bg-zap-composicao"
                >
                  {acao}
                </button>
              ))}
            </div>
          )}

          <div ref={fim} />
        </div>

        <form
          className="flex items-end gap-1.5 bg-zap-composicao px-2 py-2"
          onSubmit={(e) => {
            e.preventDefault()
            enviar(rascunho)
          }}
        >
          {/* `min-w-0` e o que deixa a pilula encolher: sem isso o campo
              empurra o botao de envio para fora da moldura. */}
          <div className="flex min-w-0 flex-1 items-center gap-1 rounded-[1.6rem] bg-zap-recebida px-2 py-1 shadow-sm">
            <span className="grid h-8 w-8 shrink-0 place-items-center text-zap-hora">
              <IconeEmoji className="h-5 w-5" />
            </span>
            <label htmlFor="mensagem" className="sr-only">
              Escreva sua mensagem
            </label>
            <input
              id="mensagem"
              value={rascunho}
              onChange={(e) => setRascunho(e.target.value)}
              placeholder="Mensagem"
              autoComplete="off"
              className="min-w-0 flex-1 bg-transparent py-1.5 text-[0.95rem] text-zap-texto outline-none placeholder:text-zap-hora"
            />
            <span className="grid h-8 w-8 shrink-0 place-items-center text-zap-hora">
              <IconeClipe className="h-5 w-5" />
            </span>
            {!temRascunho && (
              <span className="grid h-8 w-8 shrink-0 place-items-center text-zap-hora">
                <IconeCamera className="h-5 w-5" />
              </span>
            )}
          </div>

          <button
            type="submit"
            disabled={!temRascunho}
            className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-zap-envio text-white shadow-sm transition-opacity disabled:opacity-100"
            aria-label={temRascunho ? 'Enviar mensagem' : 'Gravar áudio'}
          >
            {temRascunho ? (
              <IconeEnviar className="h-5 w-5" />
            ) : (
              <IconeMicrofone className="h-5 w-5" />
            )}
          </button>
        </form>
      </div>
    </div>
  )
}

/** Barra de status do aparelho: hora, sinal, wi-fi e bateria. */
function BarraDeStatus() {
  const [hora, setHora] = useState(agora)

  useEffect(() => {
    const id = setInterval(() => setHora(agora()), 30_000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="flex items-center justify-between bg-zap-barra-escura px-6 py-1.5 text-[0.7rem] font-semibold text-white">
      <span>{hora}</span>
      <span className="flex items-center gap-1.5">
        <IconeSinal />
        <IconeWifi />
        <IconeBateria />
      </span>
    </div>
  )
}

/** Pílula central: divisor de data e aviso do sistema. */
function Etiqueta({
  children,
  className,
}: {
  children: React.ReactNode
  className: string
}) {
  return (
    <p
      className={`mx-auto w-fit max-w-[90%] rounded-lg px-3 py-1 text-center text-[0.7rem] leading-snug shadow-sm ${className}`}
    >
      {children}
    </p>
  )
}

function BalaoMensagem({ balao }: { balao: Balao }) {
  const enviada = balao.direcao === 'entrada'
  return (
    <div className={enviada ? 'flex justify-end' : 'flex justify-start'}>
      <div
        className={[
          'relative max-w-[85%] rounded-lg px-2.5 pt-1.5 pb-1 text-[0.925rem] leading-snug text-zap-texto shadow-sm',
          enviada
            ? 'zap-rabo-enviada mr-2 rounded-tr-none bg-zap-enviada'
            : 'zap-rabo-recebida ml-2 rounded-tl-none bg-zap-recebida',
        ].join(' ')}
      >
        <p
          className="break-words whitespace-pre-wrap"
          dangerouslySetInnerHTML={{ __html: comNegrito(balao.texto) }}
        />

        {balao.fontes && balao.fontes.length > 0 && (
          <p className="mt-1.5 border-t border-zap-divisor pt-1 text-[0.7rem] text-zap-hora">
            {balao.fontes.map((f) => f.documento).join(' · ')}
          </p>
        )}

        {/* A hora corre junto do texto, como no app: ela ocupa o fim da
            última linha quando cabe, e desce sozinha quando não cabe. */}
        <span className="float-right mt-0.5 ml-2 flex translate-y-0.5 items-center gap-1 text-[0.6875rem] text-zap-hora">
          {balao.hora}
          {enviada && (
            <IconeTiques className="h-3 w-4 text-zap-tique" titulo="Lida" />
          )}
        </span>
        <span className="clear-both block" />
      </div>
    </div>
  )
}
