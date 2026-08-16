/**
 * Peças reutilizadas pelas telas. Existem para que o padrão visual seja
 * herdado, e não recopiado — regra que muda aqui muda em todo lugar.
 */

type Filho = { children: React.ReactNode }

/**
 * Título de seção no padrão institucional: texto à esquerda, régua ciano
 * ocupando o resto da largura.
 */
export function TituloSecao({
  children,
  nivel = 2,
  acao,
}: Filho & { nivel?: 2 | 3; acao?: React.ReactNode }) {
  const Tag = nivel === 2 ? 'h2' : 'h3'
  return (
    <div className="flex items-center gap-4">
      <Tag
        className={
          nivel === 2
            ? 'text-lg font-bold tracking-wide uppercase'
            : 'text-sm font-bold tracking-wider uppercase'
        }
      >
        {children}
      </Tag>
      <hr className="regua-ciano" aria-hidden />
      {acao}
    </div>
  )
}

/** Cabeçalho de conteúdo: faixa azul, a cor dominante do sistema. */
export function CabecalhoConteudo({
  titulo,
  chapeu,
  descricao,
  acao,
}: {
  titulo: string
  chapeu?: string
  descricao?: string
  acao?: React.ReactNode
}) {
  return (
    <header className="rounded-[--radius-card] bg-azul px-6 py-5 text-sobre-azul">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          {chapeu && (
            <p className="text-xs font-semibold tracking-[0.18em] text-sobre-azul/80 uppercase">
              {chapeu}
            </p>
          )}
          <h1 className="mt-1 text-2xl font-bold tracking-wide text-sobre-azul uppercase">
            {titulo}
          </h1>
          {descricao && (
            <p className="mt-2 max-w-2xl text-sm text-sobre-azul/90">{descricao}</p>
          )}
        </div>
        {acao}
      </div>
    </header>
  )
}

export function Cartao({
  children,
  className = '',
}: Filho & { className?: string }) {
  return (
    <div
      className={`rounded-[--radius-card] border border-borda bg-superficie p-5 shadow-sm ${className}`}
    >
      {children}
    </div>
  )
}

type TomBotao = 'primario' | 'secundario' | 'proativo' | 'perigo'

const ESTILO_BOTAO: Record<TomBotao, string> = {
  primario: 'bg-azul text-sobre-azul hover:bg-azul-escuro',
  secundario: 'border border-borda bg-superficie text-azul-titulo hover:bg-azul-100',
  // Teal identifica tudo que é proativo/antecipação.
  proativo: 'bg-teal text-sobre-azul hover:opacity-90',
  perigo: 'border border-erro text-erro hover:bg-erro/5',
}

export function Botao({
  children,
  tom = 'primario',
  ...resto
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { tom?: TomBotao }) {
  return (
    <button
      {...resto}
      className={`rounded-[--radius-controle] px-4 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${ESTILO_BOTAO[tom]} ${resto.className ?? ''}`}
    >
      {children}
    </button>
  )
}

type TomEtiqueta = 'neutro' | 'azul' | 'proativo' | 'alerta' | 'sucesso'

const ESTILO_ETIQUETA: Record<TomEtiqueta, string> = {
  neutro: 'bg-superficie-alt text-texto-suave',
  azul: 'bg-azul-100 text-azul-titulo',
  proativo: 'bg-teal/10 text-teal',
  alerta: 'bg-alerta/10 text-alerta',
  sucesso: 'bg-sucesso/10 text-sucesso',
}

export function Etiqueta({
  children,
  tom = 'neutro',
}: Filho & { tom?: TomEtiqueta }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${ESTILO_ETIQUETA[tom]}`}
    >
      {children}
    </span>
  )
}

/** Campo de formulário com rótulo sempre presente. */
export function Campo({
  id,
  rotulo,
  ajuda,
  children,
}: Filho & { id: string; rotulo: string; ajuda?: string }) {
  return (
    <div>
      <label htmlFor={id} className="text-sm font-semibold text-azul-titulo">
        {rotulo}
      </label>
      {ajuda && <p className="mb-1 text-xs text-texto-suave">{ajuda}</p>}
      {children}
    </div>
  )
}

export const ESTILO_ENTRADA =
  'w-full rounded-[--radius-controle] border border-borda bg-superficie px-3 text-base text-texto placeholder:text-texto-suave'

/** Estado vazio: diz o que fazer, não só que está vazio. */
export function Vazio({ children }: Filho) {
  return (
    <p className="rounded-[--radius-card] border border-dashed border-borda bg-superficie-alt p-6 text-sm text-texto-suave">
      {children}
    </p>
  )
}

/** Indicador "ao vivo" — ponto ciano pulsando. */
export function AoVivo({ ativo, rotulo }: { ativo: boolean; rotulo: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <span
        className={`h-2 w-2 rounded-full ${ativo ? 'bg-ciano pulso' : 'bg-borda'}`}
        aria-hidden
      />
      {rotulo}
    </span>
  )
}
