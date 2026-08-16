import { useState } from 'react'
import ComoDecide from './ComoDecide'
import Console from './Console'
import EspelhoWhatsApp from './EspelhoWhatsApp'
import FilaServidor from './FilaServidor'
import Indicadores from './Indicadores'
import RadarCausas from './RadarCausas'
import WidgetAva from './WidgetAva'
import {
  IconeBalanca,
  IconeConsole,
  IconeConversa,
  IconeFila,
  IconeGrafico,
  IconeMenu,
  IconePagina,
  IconeRadar,
} from './componentes/Icones'
import Marca, { ASSINATURA, SLOGAN } from './componentes/Marca'
import { Campo, ESTILO_ENTRADA } from './componentes/Ui'

type Superficie =
  | 'whatsapp'
  | 'ava'
  | 'fila'
  | 'radar'
  | 'indicadores'
  | 'decide'
  | 'console'

/** Participante fictício com 2FA pendente — cai direto no cenário útil. */
const HANDLE_DEMO = '+556990000001'

const NAVEGACAO: {
  chave: Superficie
  rotulo: string
  grupo: string
  Icone: (p: { className?: string }) => React.ReactElement
}[] = [
  { chave: 'whatsapp', rotulo: 'WhatsApp', grupo: 'Participante', Icone: IconeConversa },
  { chave: 'ava', rotulo: 'Widget do AVA', grupo: 'Participante', Icone: IconePagina },
  { chave: 'fila', rotulo: 'Fila do Servidor', grupo: 'Equipe', Icone: IconeFila },
  { chave: 'radar', rotulo: 'Radar de Causas', grupo: 'Gestão', Icone: IconeRadar },
  { chave: 'indicadores', rotulo: 'Indicadores', grupo: 'Gestão', Icone: IconeGrafico },
  { chave: 'decide', rotulo: 'Como decide', grupo: 'Gestão', Icone: IconeBalanca },
  { chave: 'console', rotulo: 'Console', grupo: 'Apresentação', Icone: IconeConsole },
]

const GRUPOS = ['Participante', 'Equipe', 'Gestão', 'Apresentação']

export default function App() {
  const [superficie, setSuperficie] = useState<Superficie>('whatsapp')
  const [handle, setHandle] = useState(HANDLE_DEMO)
  const [menuAberto, setMenuAberto] = useState(false)

  const superficieDoParticipante = superficie === 'whatsapp' || superficie === 'ava'

  function navegar(destino: Superficie) {
    setSuperficie(destino)
    setMenuAberto(false)
  }

  return (
    <div className="flex min-h-screen flex-col bg-fundo">
      {/* Barra superior fixa — marinho, a primeira das três áreas que o usam. */}
      <header className="sticky top-0 z-30 bg-marinho">
        <div className="mx-auto flex max-w-[90rem] items-center gap-4 px-4 py-3 sm:px-6">
          <button
            onClick={() => setMenuAberto((v) => !v)}
            className="text-sobre-azul lg:hidden"
            aria-label={menuAberto ? 'Fechar menu' : 'Abrir menu'}
            aria-expanded={menuAberto}
          >
            <IconeMenu className="h-6 w-6" />
          </button>

          <Marca />

          <p className="ml-auto hidden max-w-md text-right text-xs text-sobre-azul/70 italic xl:block">
            {SLOGAN}
          </p>
        </div>
        {/* Régua ciano: acento fino que separa a barra do conteúdo. */}
        <div className="h-0.5 bg-ciano" aria-hidden />
      </header>

      <div className="mx-auto flex w-full max-w-[90rem] flex-1 lg:gap-8 lg:px-6">
        {/* Sidebar — segunda área marinho. */}
        <nav
          aria-label="Superfícies"
          className={[
            'bg-marinho lg:sticky lg:top-[4.25rem] lg:mt-6 lg:h-fit lg:w-64 lg:shrink-0 lg:rounded-[--radius-card]',
            menuAberto ? 'block' : 'hidden lg:block',
          ].join(' ')}
        >
          <ul className="space-y-1 p-3">
            {GRUPOS.map((grupo) => (
              <li key={grupo}>
                <p className="px-3 pt-3 pb-1 text-[0.6875rem] font-bold tracking-[0.16em] text-sobre-azul/50 uppercase">
                  {grupo}
                </p>
                <ul>
                  {NAVEGACAO.filter((i) => i.grupo === grupo).map(
                    ({ chave, rotulo, Icone }) => {
                      const ativa = superficie === chave
                      return (
                        <li key={chave}>
                          <button
                            onClick={() => navegar(chave)}
                            aria-current={ativa ? 'page' : undefined}
                            className={[
                              'flex w-full items-center gap-3 rounded-[--radius-controle] px-3 text-left text-sm font-medium transition-colors',
                              ativa
                                ? 'bg-azul text-sobre-azul'
                                : 'text-sobre-azul/80 hover:bg-azul/40',
                            ].join(' ')}
                          >
                            <Icone className="h-5 w-5 shrink-0" />
                            <span className="truncate">{rotulo}</span>
                            {ativa && (
                              <span
                                className="ml-auto h-4 w-1 rounded-full bg-ciano"
                                aria-hidden
                              />
                            )}
                          </button>
                        </li>
                      )
                    },
                  )}
                </ul>
              </li>
            ))}
          </ul>
        </nav>

        <main className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-0">
          {superficieDoParticipante && (
            <div className="mb-6 w-full sm:max-w-[26rem]">
              <Campo
                id="handle"
                rotulo="Identificação no canal"
                ajuda={
                  handle
                    ? 'Contato conhecido: o FAROL responde sobre o caso desta pessoa.'
                    : 'Anônimo: apenas informação pública, nenhum dado pessoal.'
                }
              >
                <input
                  id="handle"
                  value={handle}
                  onChange={(e) => setHandle(e.target.value)}
                  placeholder="Deixe vazio para conversar como anônimo"
                  className={`${ESTILO_ENTRADA} mt-1`}
                />
              </Campo>
            </div>
          )}

          {superficie === 'whatsapp' && (
            <EspelhoWhatsApp key={handle} handle={handle} />
          )}
          {superficie === 'ava' && <PaginaAva handle={handle} />}
          {superficie === 'fila' && <FilaServidor />}
          {superficie === 'radar' && <RadarCausas />}
          {superficie === 'indicadores' && <Indicadores />}
          {superficie === 'decide' && <ComoDecide />}
          {superficie === 'console' && (
            <Console
              handleAtual={handle}
              aoEscolherParticipante={(telefone) => {
                setHandle(telefone)
                setSuperficie('whatsapp')
              }}
            />
          )}
        </main>
      </div>

      {/* Rodapé — terceira e última área marinho. */}
      <footer className="mt-10 bg-marinho">
        <div className="h-0.5 bg-ciano" aria-hidden />
        <div className="mx-auto max-w-[90rem] px-4 py-8 sm:px-6">
          <Marca />
          <p className="mt-4 max-w-2xl text-sm text-sobre-azul/80 italic">{SLOGAN}</p>
          <p className="mt-4 text-xs text-sobre-azul/60">
            Seção de Coordenação de Educação a Distância · {ASSINATURA} · Dados
            fictícios, conforme a regra do desafio.
          </p>
        </div>
      </footer>
    </div>
  )
}

/** Simula a página do AVA em que o widget vive, para dar contexto real. */
function PaginaAva({ handle }: { handle: string }) {
  const pagina = 'Direito Digital e Proteção de Dados — Módulo 2'

  return (
    <>
      <article className="rounded-[--radius-card] border border-borda bg-superficie p-6 sm:p-8">
        <p className="text-xs font-semibold tracking-[0.16em] text-texto-suave uppercase">
          Ambiente Virtual de Aprendizagem
        </p>
        <h2 className="mt-1 text-xl font-bold tracking-wide uppercase">{pagina}</h2>
        <div className="mt-4 h-0.5 w-24 bg-ciano" aria-hidden />

        <div className="mt-6 space-y-3" aria-hidden>
          <div className="h-3 w-3/4 rounded bg-superficie-alt" />
          <div className="h-3 w-full rounded bg-superficie-alt" />
          <div className="h-3 w-5/6 rounded bg-superficie-alt" />
          <div className="h-32 rounded bg-superficie-alt" />
          <div className="h-3 w-2/3 rounded bg-superficie-alt" />
        </div>

        <p className="mt-6 text-sm text-texto-suave">
          O widget conhece a página em que a pessoa está e envia esse contexto
          junto da pergunta.
        </p>
      </article>

      <WidgetAva handle={handle} pagina={pagina} />
    </>
  )
}
