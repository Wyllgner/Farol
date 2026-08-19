import { useState } from 'react'
import WidgetAva from './WidgetAva'
import { TituloSecao } from './componentes/Ui'

/**
 * As duas telas do AVA onde o widget vive.
 *
 * Elas existem separadas porque provam coisas diferentes. A tela de login
 * responde à pergunta que sempre aparece primeiro — "isso só funciona
 * para quem já conseguiu entrar?" — e a resposta é não: sem identidade o
 * FAROL responde o que é público, que é exatamente o que resolve o
 * problema de quem está travado ANTES do login. A tela de dentro do AVA
 * mostra o outro extremo, onde o widget sabe quem é a pessoa e em que
 * página ela está.
 *
 * O fundo é um print do AVA real, posto num arquivo do projeto. Nada aqui
 * tenta redesenhar a plataforma da Escola: o que se demonstra é o widget
 * sobre ela.
 */

type Cena = 'login' | 'dentro'

/** Print da tela de login do AVA. Basta soltar o arquivo em `public/`. */
const IMAGEM_LOGIN = '/ava-login.png'

const ENDERECO_LOGIN = 'ava.emeron.jus.br/login'
const ENDERECO_CURSO = 'ava.emeron.jus.br/curso/direito-digital/modulo-2'

const CENAS: { chave: Cena; rotulo: string; explica: string }[] = [
  {
    chave: 'login',
    rotulo: 'Tela de login',
    explica:
      'Antes de entrar, sem identidade nenhuma. O FAROL responde o que é público e não pede cadastro para ajudar: quem não consegue fazer login é justamente quem mais precisa de resposta.',
  },
  {
    chave: 'dentro',
    rotulo: 'Dentro do AVA',
    explica:
      'Depois de entrar. O widget sabe em que página a pessoa está e responde sobre o caso dela, com o estado da matrícula.',
  },
]

export default function TelasAva({ handle }: { handle: string }) {
  const [cena, setCena] = useState<Cena>('login')
  const atual = CENAS.find((c) => c.chave === cena)!

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div
          role="tablist"
          aria-label="Telas do AVA"
          className="inline-flex rounded-full border border-borda bg-superficie p-1"
        >
          {CENAS.map(({ chave, rotulo }) => (
            <button
              key={chave}
              role="tab"
              aria-selected={cena === chave}
              onClick={() => setCena(chave)}
              className={[
                'rounded-full px-4 py-1.5 text-sm font-semibold transition-colors',
                cena === chave
                  ? 'bg-azul text-sobre-azul'
                  : 'text-azul-titulo hover:bg-azul-100',
              ].join(' ')}
            >
              {rotulo}
            </button>
          ))}
        </div>
      </div>

      <p className="max-w-3xl text-sm text-texto-suave">{atual.explica}</p>

      {cena === 'login' ? (
        <Navegador endereco={ENDERECO_LOGIN}>
          <PrintDoAva
            src={IMAGEM_LOGIN}
            alt="Tela de login do Ambiente Virtual de Aprendizagem da EMERON"
          />
          {/* Handle vazio de propósito: nesta tela a pessoa ainda não é
              ninguém para o sistema, e é isso que se demonstra. */}
          {/* `key` por cena: sem ele o React reaproveita a mesma instância
              ao trocar de aba e o widget herda o estado da outra tela,
              chegando aberto e com a conversa anterior. */}
          <WidgetAva
            key="login"
            handle=""
            pagina="Tela de login do AVA"
            ancorado
            iniciarAberto
          />
        </Navegador>
      ) : (
        <Navegador endereco={ENDERECO_CURSO}>
          <PaginaDoCurso />
          <WidgetAva
            key="dentro"
            handle={handle}
            pagina="Direito Digital e Proteção de Dados: Módulo 2"
            ancorado
          />
        </Navegador>
      )}
    </div>
  )
}

/**
 * Moldura de navegador em volta da cena.
 *
 * Sem ela o print vira uma imagem solta na página e o widget parece um
 * componente do FAROL. Com ela, fica claro o que é a plataforma da Escola
 * e o que é a camada que estamos propondo por cima.
 */
function Navegador({
  endereco,
  children,
}: {
  endereco: string
  children: React.ReactNode
}) {
  return (
    <div className="overflow-hidden rounded-[--radius-card] border border-borda bg-superficie shadow-lg">
      <div className="flex items-center gap-3 border-b border-borda bg-superficie-alt px-4 py-2.5">
        <span className="flex gap-1.5" aria-hidden>
          {['bg-erro/70', 'bg-alerta/70', 'bg-sucesso/70'].map((cor) => (
            <span key={cor} className={`h-3 w-3 rounded-full ${cor}`} />
          ))}
        </span>
        <span className="flex-1 truncate rounded-full bg-superficie px-3 py-1 text-xs text-texto-suave">
          {endereco}
        </span>
      </div>

      {/* `relative` é o que prende o widget a esta moldura. */}
      <div className="relative min-h-[30rem] bg-superficie-alt">{children}</div>
    </div>
  )
}

/**
 * O print da plataforma, com instrução no lugar dele enquanto não existe.
 *
 * O arquivo é do próprio usuário e entra depois; até lá a tela precisa
 * dizer o que falta, e não quebrar com um ícone de imagem partida.
 */
function PrintDoAva({ src, alt }: { src: string; alt: string }) {
  const [falhou, setFalhou] = useState(false)

  if (falhou) {
    return (
      <div className="grid min-h-[30rem] place-items-center p-8">
        <div className="max-w-md rounded-[--radius-card] border-2 border-dashed border-borda p-6 text-center">
          <TituloSecao nivel={3}>Falta o print</TituloSecao>
          <p className="mt-3 text-sm text-texto-suave">
            Salve a captura da tela de login do AVA como{' '}
            <code className="rounded bg-superficie-alt px-1.5 py-0.5 text-texto">
              apps/web/public/ava-login.png
            </code>{' '}
            e ela aparece aqui, com o widget por cima.
          </p>
        </div>
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={alt}
      onError={() => setFalhou(true)}
      className="block w-full"
    />
  )
}

/** Página de curso simulada: contexto para o widget de dentro do AVA. */
function PaginaDoCurso() {
  return (
    <article className="p-6 sm:p-8">
      <p className="text-xs font-semibold tracking-[0.16em] text-texto-suave uppercase">
        Ambiente Virtual de Aprendizagem
      </p>
      <h2 className="mt-1 text-xl font-bold tracking-wide uppercase">
        Direito Digital e Proteção de Dados: Módulo 2
      </h2>
      <div className="mt-4 h-0.5 w-24 bg-ciano" aria-hidden />

      <div className="mt-6 space-y-3" aria-hidden>
        <div className="h-3 w-3/4 rounded bg-superficie" />
        <div className="h-3 w-full rounded bg-superficie" />
        <div className="h-3 w-5/6 rounded bg-superficie" />
        <div className="h-32 rounded bg-superficie" />
        <div className="h-3 w-2/3 rounded bg-superficie" />
      </div>

      <p className="mt-6 max-w-xl text-sm text-texto-suave">
        O widget conhece a página em que a pessoa está e envia esse contexto
        junto da pergunta.
      </p>
    </article>
  )
}
