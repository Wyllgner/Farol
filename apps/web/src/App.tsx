import { useState } from 'react'
import EspelhoWhatsApp from './EspelhoWhatsApp'
import ComoDecide from './ComoDecide'
import Console from './Console'
import FilaServidor from './FilaServidor'
import Indicadores from './Indicadores'
import RadarCausas from './RadarCausas'
import WidgetAva from './WidgetAva'

type Superficie = 'whatsapp' | 'ava' | 'fila' | 'radar' | 'indicadores' | 'decide' | 'console'

/** Participante fictício com 2FA pendente — aciona a oferta de acompanhamento. */
const HANDLE_DEMO = '+556990000001'

export default function App() {
  const [superficie, setSuperficie] = useState<Superficie>('whatsapp')
  const [handle, setHandle] = useState(HANDLE_DEMO)

  return (
    <div className="min-h-screen">
      <header className="border-b border-neutro-300 bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-6 py-4">
          <div>
            <p className="text-xs font-medium tracking-widest text-dourado-600 uppercase">
              SECOEAD · EMERON
            </p>
            <h1 className="text-2xl font-semibold text-marinho-900">FAROL</h1>
          </div>

          <nav className="flex gap-2" aria-label="Superfícies">
            <Aba
              ativa={superficie === 'whatsapp'}
              onClick={() => setSuperficie('whatsapp')}
            >
              WhatsApp
            </Aba>
            <Aba ativa={superficie === 'ava'} onClick={() => setSuperficie('ava')}>
              Widget do AVA
            </Aba>
            <Aba ativa={superficie === 'fila'} onClick={() => setSuperficie('fila')}>
              Fila do Servidor
            </Aba>
            <Aba ativa={superficie === 'radar'} onClick={() => setSuperficie('radar')}>
              Radar de Causas
            </Aba>
            <Aba
              ativa={superficie === 'indicadores'}
              onClick={() => setSuperficie('indicadores')}
            >
              Indicadores
            </Aba>
            <Aba ativa={superficie === 'decide'} onClick={() => setSuperficie('decide')}>
              Como decide
            </Aba>
            <Aba
              ativa={superficie === 'console'}
              onClick={() => setSuperficie('console')}
            >
              Console
            </Aba>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-10">
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

        {(superficie === 'whatsapp' || superficie === 'ava') && (
        <label className="mb-8 block max-w-md">
          <span className="text-sm font-medium text-neutro-600">
            Identificação no canal
          </span>
          <input
            value={handle}
            onChange={(e) => setHandle(e.target.value)}
            placeholder="Deixe vazio para conversar como anônimo"
            className="mt-1 min-h-[44px] w-full rounded-[--radius-suave] border border-neutro-300 px-3 text-base"
          />
          <span className="mt-1 block text-sm text-neutro-600">
            {handle
              ? 'Contato conhecido: o FAROL responde sobre o caso desta pessoa.'
              : 'Anônimo: só informação pública, nenhum dado pessoal.'}
          </span>
        </label>
        )}

        {superficie === 'whatsapp' && <EspelhoWhatsApp key={handle} handle={handle} />}
        {superficie === 'ava' && <PaginaAva handle={handle} />}
      </main>
    </div>
  )
}

function Aba({
  ativa,
  onClick,
  children,
}: {
  ativa: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      aria-current={ativa ? 'page' : undefined}
      className={[
        'rounded-[--radius-suave] px-4 text-sm font-medium',
        ativa
          ? 'bg-marinho-700 text-white'
          : 'border border-neutro-300 text-neutro-600',
      ].join(' ')}
    >
      {children}
    </button>
  )
}

/** Simula a página do AVA em que o widget vive, para dar contexto real. */
function PaginaAva({ handle }: { handle: string }) {
  const pagina = 'Direito Digital e Proteção de Dados — Módulo 2'

  return (
    <>
      <article className="rounded-[--radius-suave] border border-neutro-300 bg-white p-8">
        <p className="text-xs tracking-widest text-neutro-600 uppercase">
          Ambiente Virtual de Aprendizagem
        </p>
        <h2 className="mt-1 text-xl font-semibold text-marinho-900">{pagina}</h2>

        <div className="mt-6 space-y-3 text-neutro-600">
          <div className="h-3 w-3/4 rounded bg-neutro-100" />
          <div className="h-3 w-full rounded bg-neutro-100" />
          <div className="h-3 w-5/6 rounded bg-neutro-100" />
          <div className="h-32 rounded bg-neutro-100" />
          <div className="h-3 w-2/3 rounded bg-neutro-100" />
        </div>

        <p className="mt-6 text-sm text-neutro-600">
          O widget conhece a página em que a pessoa está e envia esse contexto
          junto da pergunta.
        </p>
      </article>

      <WidgetAva handle={handle} pagina={pagina} />
    </>
  )
}
