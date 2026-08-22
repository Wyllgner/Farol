import { useState } from 'react'
import ComoDecide from './ComoDecide'
import Console from './Console'
import EspelhoWhatsApp from './EspelhoWhatsApp'
import FilaServidor from './FilaServidor'
import Indicadores from './Indicadores'
import RadarCausas from './RadarCausas'
import TelasAva from './TelasAva'
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
import Marca from './componentes/Marca'
import PortaoRestrito from './componentes/PortaoRestrito'
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
// Dra. Ana Beatriz Moraes: a personagem do roteiro de demonstracao. Ela e o
// padrao para que ninguem precise digitar o numero no palco. Cada tecla
// digitada aqui recria o espelho e, com ele, a conexao do canal.
const HANDLE_DEMO = '+556990000000'

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
  // O espelho ganha palco escuro: sem nada em volta, o celular vira o
  // unico objeto na tela, que e exatamente o que a demonstracao precisa
  // que a banca olhe.
  const palco = superficie === 'whatsapp'

  function navegar(destino: Superficie) {
    setSuperficie(destino)
    setMenuAberto(false)
  }

  return (
    <div className="flex min-h-screen flex-col bg-fundo">
      {/* Barra superior so no celular. No desktop a marca vive no topo da
          barra lateral e esta faixa nao existe; aqui ela sobrevive porque e
          o unico lugar de onde o menu recolhido pode ser aberto. */}
      <header className="sticky top-0 z-30 bg-marinho lg:hidden">
        <div className="flex items-center gap-4 px-4 py-3 sm:px-6">
          <button
            onClick={() => setMenuAberto((v) => !v)}
            className="text-sobre-azul"
            aria-label={menuAberto ? 'Fechar menu' : 'Abrir menu'}
            aria-expanded={menuAberto}
          >
            <IconeMenu className="h-6 w-6" />
          </button>

          <Marca />
        </div>
        <div className="h-0.5 bg-ciano" aria-hidden />
      </header>

      <div className="flex w-full flex-1">
        {/* Sidebar: segunda area marinho. */}
        <nav
          aria-label="Superfícies"
          className={[
            // Colada na margem esquerda e presa ao topo em todas as telas: a
            // navegacao e o mapa da demonstracao, e um mapa que some quando a
            // pagina rola nao serve para quem apresenta. A faixa marinho
            // acompanha a altura da pagina; a lista dentro dela e que fica
            // presa ao topo. Prender a faixa inteira empurrava os primeiros
            // itens para fora da tela quando o conteudo era curto.
            'bg-marinho lg:w-64 lg:shrink-0 lg:self-stretch',
            menuAberto ? 'block' : 'hidden lg:block',
          ].join(' ')}
        >
          <div className="lg:sticky lg:top-0">
            {/* A marca abre a lateral no desktop: sem barra superior, e daqui
                que o produto se identifica. */}
            <div className="hidden px-4 pt-5 pb-4 lg:block">
              <Marca assinaturaEmDuasLinhas />
            </div>
            <div className="mx-4 hidden h-0.5 bg-ciano lg:block" aria-hidden />

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
          </div>
        </nav>

        <main
          className={[
            // Folga maior embaixo que em cima: sem rodape, o ultimo cartao
            // encostava na borda da janela e a pagina parecia cortada.
            'min-w-0 flex-1 px-4 pt-6 pb-16 sm:px-6',
            // Fundo levemente tingido nas telas de trabalho: cartao branco
            // sobre pagina branca nao separa nada, e a tela inteira vira uma
            // folha continua onde nada tem comeco nem fim.
            palco ? 'zap-palco flex flex-col items-center gap-5' : 'bg-superficie-alt',
          ].join(' ')}
        >
          {superficieDoParticipante &&
            (palco ? (
              <IdentificacaoNoPalco handle={handle} aoMudar={setHandle} />
            ) : (
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
            ))}

          {superficie === 'whatsapp' && (
            <EspelhoWhatsApp key={handle} handle={handle} />
          )}
          {superficie === 'ava' && <TelasAva handle={handle} />}
          {superficie === 'fila' && <FilaServidor />}
          {superficie === 'radar' && <RadarCausas />}
          {superficie === 'indicadores' && <Indicadores />}
          {/* As duas superficies restritas. O portao e conveniencia de
              interface: quem protege de verdade e o 401 do servidor. */}
          {superficie === 'decide' && (
            <PortaoRestrito titulo="Como o FAROL decide">
              <ComoDecide />
            </PortaoRestrito>
          )}
          {superficie === 'console' && (
            <PortaoRestrito titulo="Console de Demonstração">
              <Console
                handleAtual={handle}
                aoEscolherParticipante={(telefone) => {
                  setHandle(telefone)
                  setSuperficie('whatsapp')
                }}
              />
            </PortaoRestrito>
          )}
        </main>
      </div>
    </div>
  )
}

/**
 * Identificação do contato sobre o palco escuro.
 *
 * O componente `Campo` padrao tem rotulo azul-marinho sobre fundo claro:
 * jogado no palco ele vira um cartao branco brigando com a cena. Aqui os
 * mesmos tres elementos usam a paleta do palco.
 */
function IdentificacaoNoPalco({
  handle,
  aoMudar,
}: {
  handle: string
  aoMudar: (v: string) => void
}) {
  return (
    <div className="w-full sm:max-w-[26rem]">
      <label
        htmlFor="handle"
        className="text-[0.6875rem] font-semibold tracking-[0.16em] text-zap-palco-suave uppercase"
      >
        Identificação no canal
      </label>
      <input
        id="handle"
        value={handle}
        onChange={(e) => aoMudar(e.target.value)}
        placeholder="Deixe vazio para conversar como anônimo"
        className="mt-1.5 w-full rounded-full border border-zap-palco-borda bg-zap-palco-campo px-4 py-2 text-sm text-zap-palco-texto placeholder:text-zap-palco-suave/70"
      />
      <p className="mt-1.5 text-xs text-zap-palco-suave">
        {handle
          ? 'Contato conhecido: o FAROL responde sobre o caso desta pessoa.'
          : 'Anônimo: apenas informação pública, nenhum dado pessoal.'}
      </p>
    </div>
  )
}

