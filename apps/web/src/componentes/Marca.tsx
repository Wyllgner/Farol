import { IconeFarol } from './Icones'

export const SLOGAN =
  'Responde antes da pergunta. E trabalha para nunca mais precisar responder.'

export const ASSINATURA = 'EMERON · Transformando a Justiça pela Educação'

type Props = {
  /** `sobre-escuro` para a barra marinho; `sobre-claro` para o conteúdo. */
  tom?: 'sobre-escuro' | 'sobre-claro'
  tamanho?: 'normal' | 'grande'
}

export default function Marca({ tom = 'sobre-escuro', tamanho = 'normal' }: Props) {
  const claro = tom === 'sobre-escuro'
  const grande = tamanho === 'grande'

  return (
    <div className="flex items-center gap-3">
      {/* Ícone em traço branco sobre azul, como os cartões de acesso rápido. */}
      <span
        className={[
          'grid shrink-0 place-items-center rounded-[--radius-controle] text-sobre-azul',
          grande ? 'h-14 w-14' : 'h-10 w-10',
          claro ? 'bg-azul' : 'bg-azul',
        ].join(' ')}
      >
        <IconeFarol className={grande ? 'h-8 w-8' : 'h-6 w-6'} />
      </span>

      <span className="min-w-0">
        <span
          className={[
            'block font-bold tracking-wide uppercase',
            grande ? 'text-3xl' : 'text-xl',
            claro ? 'text-sobre-azul' : 'text-azul-titulo',
          ].join(' ')}
        >
          Farol
        </span>
        <span
          className={[
            'block truncate text-xs italic',
            claro ? 'text-sobre-azul/80' : 'text-texto-suave',
          ].join(' ')}
        >
          {ASSINATURA}
        </span>
      </span>
    </div>
  )
}
