/**
 * Ícones em traço, mesmo peso de linha do livro aberto da marca EMERON.
 * Sem preenchimento, `currentColor` sempre: a cor vem do contexto, nunca
 * do ícone.
 */

type Props = { className?: string; titulo?: string }

function Svg({
  children,
  className = 'h-5 w-5',
  titulo,
}: Props & { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      role={titulo ? 'img' : 'presentation'}
      aria-label={titulo}
      aria-hidden={titulo ? undefined : true}
    >
      {children}
    </svg>
  )
}

/**
 * O farol: cobertura, lanterna, torre afunilada, base e os dois feixes.
 * Desenhado para continuar legível a 20px: a versão anterior virava um
 * rabisco no tamanho em que de fato aparece.
 */
export function IconeFarol(props: Props) {
  return (
    <Svg {...props}>
      {/* telhado */}
      <path d="M9.4 6.3L12 3.4l2.6 2.9" />
      {/* lanterna */}
      <path d="M9.9 6.3h4.2v3.3H9.9z" />
      {/* torre afunilando + faixa: e a faixa que diz "farol" */}
      <path d="M10.1 9.6L8.6 19M13.9 9.6l1.5 9.4" />
      <path d="M9.4 13.6h5.2" />
      {/* base */}
      <path d="M7.2 19h9.6" />
      {/* feixes, curtos e inclinados para cima */}
      <path d="M8.4 7.2L5.8 6.1M15.6 7.2l2.6-1.1" />
    </Svg>
  )
}

export function IconeConversa(props: Props) {
  return (
    <Svg {...props}>
      <path d="M20 14.5a2.5 2.5 0 0 1-2.5 2.5H8l-4 3.5V6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5z" />
    </Svg>
  )
}

export function IconePagina(props: Props) {
  return (
    <Svg {...props}>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" />
      <path d="M9 13h6M9 17h4" />
    </Svg>
  )
}

export function IconeFila(props: Props) {
  return (
    <Svg {...props}>
      <path d="M4 6h16M4 12h16M4 18h10" />
      <circle cx="19" cy="18" r="2" />
    </Svg>
  )
}

export function IconeRadar(props: Props) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="4.5" />
      <path d="M12 12l6-4" />
    </Svg>
  )
}

export function IconeGrafico(props: Props) {
  return (
    <Svg {...props}>
      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
    </Svg>
  )
}

export function IconeBalanca(props: Props) {
  return (
    <Svg {...props}>
      <path d="M12 4v16M7 20h10" />
      <path d="M5 8h14" />
      <path d="M5 8l-2.5 5a2.5 2.5 0 0 0 5 0z" />
      <path d="M19 8l2.5 5a2.5 2.5 0 0 1-5 0z" />
    </Svg>
  )
}

export function IconeConsole(props: Props) {
  return (
    <Svg {...props}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M7 9l3 3-3 3M13 15h4" />
    </Svg>
  )
}

export function IconeEnviar(props: Props) {
  return (
    <Svg {...props}>
      <path d="M4 12l16-8-6 16-2.5-6.5z" />
    </Svg>
  )
}

export function IconeFonte(props: Props) {
  return (
    <Svg {...props}>
      <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H10a2 2 0 0 1 2 2v13a2 2 0 0 0-2-2H5.5A1.5 1.5 0 0 1 4 15.5z" />
      <path d="M20 5.5A1.5 1.5 0 0 0 18.5 4H14a2 2 0 0 0-2 2v13a2 2 0 0 1 2-2h4.5a1.5 1.5 0 0 0 1.5-1.5z" />
    </Svg>
  )
}

export function IconeFechar(props: Props) {
  return (
    <Svg {...props}>
      <path d="M6 6l12 12M18 6L6 18" />
    </Svg>
  )
}

export function IconeMenu(props: Props) {
  return (
    <Svg {...props}>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </Svg>
  )
}

/* ==========================================================================
   Ícones do espelho do WhatsApp
   Redesenhados no mesmo traço dos demais, e não copiados do app: o
   espelho reproduz o comportamento e a sensação da interface, sem
   redistribuir o material gráfico da Meta.
   ========================================================================== */

export function IconeVoltar(props: Props) {
  return (
    <Svg {...props}>
      <path d="M19 12H5" />
      <path d="m12 19-7-7 7-7" />
    </Svg>
  )
}

export function IconeVideo(props: Props) {
  return (
    <Svg {...props}>
      <rect x="3" y="6" width="12" height="12" rx="2.5" />
      <path d="m15 11 6-3.5v9L15 13z" />
    </Svg>
  )
}

export function IconeChamada(props: Props) {
  return (
    <Svg {...props}>
      <path d="M6.5 3.5h3l1.5 4-2 1.5a12 12 0 0 0 6 6l1.5-2 4 1.5v3a2 2 0 0 1-2.2 2A17 17 0 0 1 4.5 5.7 2 2 0 0 1 6.5 3.5Z" />
    </Svg>
  )
}

export function IconeTresPontos(props: Props) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="5" r="1.1" fill="currentColor" />
      <circle cx="12" cy="12" r="1.1" fill="currentColor" />
      <circle cx="12" cy="19" r="1.1" fill="currentColor" />
    </Svg>
  )
}

export function IconeEmoji(props: Props) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M8.5 14.5a4.5 4.5 0 0 0 7 0" />
      <path d="M9 9.5h.01M15 9.5h.01" />
    </Svg>
  )
}

export function IconeClipe(props: Props) {
  return (
    <Svg {...props}>
      <path d="M20 11.5 12 19.5a5 5 0 0 1-7-7l8-8a3.5 3.5 0 0 1 5 5l-8 8a2 2 0 0 1-3-3l7.5-7.5" />
    </Svg>
  )
}

export function IconeCamera(props: Props) {
  return (
    <Svg {...props}>
      <path d="M3 8.5A2 2 0 0 1 5 6.5h1.8l1.2-2h8l1.2 2H19a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z" />
      <circle cx="12" cy="13" r="3.5" />
    </Svg>
  )
}

export function IconeMicrofone(props: Props) {
  return (
    <Svg {...props}>
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 12a7 7 0 0 0 14 0" />
      <path d="M12 19v2" />
    </Svg>
  )
}

/** Os dois tiques da mensagem entregue e lida. */
export function IconeTiques(props: Props) {
  return (
    <svg
      viewBox="0 0 20 12"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className ?? 'h-3.5 w-4'}
      role={props.titulo ? 'img' : 'presentation'}
      aria-label={props.titulo}
      aria-hidden={props.titulo ? undefined : true}
    >
      <path d="m1 6.6 3.2 3.2L10.4 3" />
      <path d="m8.4 9.8 6.2-6.8" />
      <path d="m12.6 6.6 1.6 1.6" />
    </svg>
  )
}

/** Sinal, wi-fi e bateria da barra de status do celular. */
export function IconeSinal(props: Props) {
  return (
    <svg
      viewBox="0 0 18 12"
      fill="currentColor"
      className={props.className ?? 'h-3 w-4'}
      aria-hidden
    >
      <rect x="0" y="8" width="3" height="4" rx="1" />
      <rect x="5" y="5.5" width="3" height="6.5" rx="1" />
      <rect x="10" y="3" width="3" height="9" rx="1" />
      <rect x="15" y="0.5" width="3" height="11.5" rx="1" opacity="0.4" />
    </svg>
  )
}

export function IconeWifi(props: Props) {
  return (
    <svg
      viewBox="0 0 18 13"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      className={props.className ?? 'h-3 w-4'}
      aria-hidden
    >
      <path d="M1 4.5a12 12 0 0 1 16 0" />
      <path d="M4 7.6a8 8 0 0 1 10 0" />
      <path d="M6.8 10.6a4 4 0 0 1 4.4 0" />
    </svg>
  )
}

export function IconeBateria(props: Props) {
  return (
    <svg
      viewBox="0 0 26 13"
      fill="none"
      className={props.className ?? 'h-3 w-6'}
      aria-hidden
    >
      <rect
        x="0.75"
        y="0.75"
        width="21"
        height="11.5"
        rx="3"
        stroke="currentColor"
        strokeWidth={1.2}
        opacity="0.5"
      />
      <rect x="2.5" y="2.5" width="14" height="8" rx="1.6" fill="currentColor" />
      <path
        d="M23.5 4.5v4a2.2 2.2 0 0 0 0-4Z"
        fill="currentColor"
        opacity="0.5"
      />
    </svg>
  )
}
