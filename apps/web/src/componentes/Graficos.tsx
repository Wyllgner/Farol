/**
 * Primitivos de gráfico, em SVG puro.
 *
 * Sem biblioteca de charting de propósito: o que o painel precisa desenhar
 * são quatro formas, e cada uma cabe em poucas dezenas de linhas. Uma
 * dependência de 200kB para isso custaria mais em peso e em superfície de
 * manutenção do que o código que ela substitui.
 *
 * Regras que valem para todos os gráficos daqui:
 *
 * - **Desenhar em pixel real, nunca em viewBox esticado.** Um viewBox de
 *   720 exibido em 1290 amplia tudo em 1,8x: a fonte de 11px vira 20px, o
 *   traço de 2px vira 3,6px, e o gráfico inteiro ganha aparência de
 *   ampliação de tela. Por isso a largura é medida e as coordenadas são
 *   calculadas em cima dela.
 * - Cor sai de `--serie-N`, na ordem fixa declarada em paleta.ts. Nenhum
 *   componente escolhe cor: a paleta foi validada para daltonismo e
 *   contraste, e escolher no olho quebra a validação em silêncio.
 * - Uma única escala vertical por gráfico. Duas séries de grandezas
 *   diferentes viram dois gráficos, nunca dois eixos.
 * - Texto usa token de texto, nunca a cor da série. A cor identifica a
 *   marca ao lado do rótulo; ela não é o rótulo.
 */

import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'

/**
 * Largura real do container, em pixels de tela.
 *
 * É o que permite desenhar sem escalar. O ResizeObserver mantém o valor
 * certo quando a janela muda de tamanho.
 */
function useLargura<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [largura, setLargura] = useState(0)

  useLayoutEffect(() => {
    const alvo = ref.current
    if (!alvo) return
    setLargura(alvo.clientWidth)
    const observador = new ResizeObserver(([e]) => setLargura(e.contentRect.width))
    observador.observe(alvo)
    return () => observador.disconnect()
  }, [])

  return [ref, largura] as const
}

/**
 * Escala "redonda" para o eixo vertical.
 *
 * Um eixo que termina em 76 obriga a ler o número para saber a escala.
 * Terminando em 80, com quatro divisões, a escala se lê pela grade — e
 * quatro linhas bastam: onze linhas viram papel quadriculado, e os dados
 * desaparecem dentro dele.
 */
function escala(maximo: number, divisoes = 4) {
  const bruto = Math.max(1, maximo) / divisoes
  const magnitude = 10 ** Math.floor(Math.log10(bruto))
  const passo = [1, 2, 2.5, 5, 10].find((m) => m * magnitude >= bruto)! * magnitude
  return {
    teto: passo * divisoes,
    marcas: Array.from({ length: divisoes + 1 }, (_, i) => i * passo),
  }
}

/** Curva suave entre pontos. O bico duro exagera cada oscilação semanal. */
function suave(
  valores: number[],
  x: (i: number) => number,
  y: (v: number) => number,
) {
  return valores
    .map((v, i) => {
      if (i === 0) return `M ${x(0)} ${y(v)}`
      const meio = (x(i - 1) + x(i)) / 2
      return `C ${meio} ${y(valores[i - 1])}, ${meio} ${y(v)}, ${x(i)} ${y(v)}`
    })
    .join(' ')
}

// --------------------------------------------------------------------------
// Legenda
// --------------------------------------------------------------------------

export function Legenda({ itens }: { itens: { rotulo: string; cor: string }[] }) {
  return (
    <ul className="flex flex-wrap items-center gap-x-5 gap-y-1.5">
      {itens.map((i) => (
        <li key={i.rotulo} className="flex items-center gap-2 text-xs text-texto-suave">
          <span
            className="inline-block h-[3px] w-4 shrink-0 rounded-full"
            style={{ background: i.cor }}
            aria-hidden
          />
          {i.rotulo}
        </li>
      ))}
    </ul>
  )
}

// --------------------------------------------------------------------------
// Linhas
// --------------------------------------------------------------------------

type Serie = { rotulo: string; valores: number[]; cor: string; area?: boolean }

/**
 * Linhas ao longo do tempo, com crosshair e tooltip.
 *
 * O hover não é enfeite: sem ele, ler "quanto foi na semana de 20/07" vira
 * estimativa a olho, e o número exato é justamente o que alguém quer
 * conferir num painel de indicadores.
 */
export function GraficoLinhas({
  rotulos,
  series,
  altura = 260,
}: {
  rotulos: string[]
  series: Serie[]
  altura?: number
}) {
  const id = useId()
  const [caixa, largura] = useLargura<HTMLDivElement>()
  const [ativo, setAtivo] = useState<number | null>(null)

  // Folga à direita para o rótulo no fim da linha, que dispensa caçar a
  // legenda para saber qual curva é qual.
  const M = { topo: 16, direita: 124, baixo: 30, esquerda: 36 }
  const areaX = Math.max(1, largura - M.esquerda - M.direita)
  const areaY = altura - M.topo - M.baixo

  const { teto, marcas } = escala(Math.max(...series.flatMap((s) => s.valores)))

  const x = (i: number) =>
    M.esquerda + (rotulos.length < 2 ? areaX / 2 : (i * areaX) / (rotulos.length - 1))
  const y = (v: number) => M.topo + areaY - (v / teto) * areaY

  const area = (valores: number[]) =>
    `${suave(valores, x, y)} L ${x(valores.length - 1)} ${M.topo + areaY} L ${x(0)} ${
      M.topo + areaY
    } Z`

  // Datas sem encavalar: seis legíveis valem mais que doze ilegíveis.
  const passoRotulo = Math.max(
    1,
    Math.ceil(rotulos.length / Math.max(1, Math.floor(areaX / 76))),
  )

  return (
    <div ref={caixa} className="relative w-full">
      {largura > 0 && (
        <svg
          width={largura}
          height={altura}
          role="img"
          aria-label={`Evolução semanal: ${series.map((s) => s.rotulo).join(', ')}`}
          onMouseLeave={() => setAtivo(null)}
        >
          <defs>
            {series.map((s, i) => (
              <linearGradient key={s.rotulo} id={`${id}-g${i}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={s.cor} stopOpacity="0.16" />
                <stop offset="100%" stopColor={s.cor} stopOpacity="0" />
              </linearGradient>
            ))}
          </defs>

          {/* Grade recessiva: orienta, não compete com os dados. */}
          {marcas.map((v) => (
            <g key={v}>
              <line
                x1={M.esquerda}
                y1={y(v)}
                x2={M.esquerda + areaX}
                y2={y(v)}
                stroke="var(--grade)"
                strokeWidth={1}
                shapeRendering="crispEdges"
              />
              <text
                x={M.esquerda - 10}
                y={y(v) + 4}
                textAnchor="end"
                fontSize={11}
                className="fill-texto-suave"
              >
                {v}
              </text>
            </g>
          ))}

          {rotulos.map((r, i) =>
            i % passoRotulo === 0 ? (
              <text
                key={`${r}-${i}`}
                x={x(i)}
                y={altura - 10}
                textAnchor="middle"
                fontSize={11}
                className="fill-texto-suave"
              >
                {r}
              </text>
            ) : null,
          )}

          {series.map((s, i) =>
            s.area ? (
              <path key={`a-${s.rotulo}`} d={area(s.valores)} fill={`url(#${id}-g${i})`} />
            ) : null,
          )}

          {series.map((s) => (
            <path
              key={s.rotulo}
              d={suave(s.valores, x, y)}
              fill="none"
              stroke={s.cor}
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ))}

          {/* Rótulo direto no fim da linha. */}
          {series.map((s) => {
            const ultimo = s.valores[s.valores.length - 1]
            return (
              <g key={`r-${s.rotulo}`}>
                <circle
                  cx={x(s.valores.length - 1)}
                  cy={y(ultimo)}
                  r={3.5}
                  fill={s.cor}
                  stroke="var(--farol-superficie)"
                  strokeWidth={2}
                />
                <text
                  x={x(s.valores.length - 1) + 12}
                  y={y(ultimo) - 2}
                  fontSize={13}
                  fontWeight={700}
                  fill={s.cor}
                >
                  {ultimo}
                </text>
                <text
                  x={x(s.valores.length - 1) + 12}
                  y={y(ultimo) + 12}
                  fontSize={10.5}
                  className="fill-texto-suave"
                >
                  {s.rotulo}
                </text>
              </g>
            )
          })}

          {ativo !== null && (
            <g pointerEvents="none">
              <line
                x1={x(ativo)}
                y1={M.topo}
                x2={x(ativo)}
                y2={M.topo + areaY}
                stroke="var(--farol-texto-suave)"
                strokeWidth={1}
                strokeDasharray="3 3"
                opacity={0.55}
              />
              {series.map((s) => (
                <circle
                  key={`p-${s.rotulo}`}
                  cx={x(ativo)}
                  cy={y(s.valores[ativo])}
                  r={4.5}
                  fill={s.cor}
                  // Anel na cor da superfície: dois pontos que se encostam
                  // continuam sendo dois pontos.
                  stroke="var(--farol-superficie)"
                  strokeWidth={2}
                />
              ))}
            </g>
          )}

          {/* Faixas de captura largas: mirar um ponto de 4px com o mouse é
              teste de pontaria, não interface. */}
          {rotulos.map((r, i) => (
            <rect
              key={`h-${r}-${i}`}
              x={x(i) - areaX / Math.max(1, rotulos.length - 1) / 2}
              y={M.topo}
              width={areaX / Math.max(1, rotulos.length - 1)}
              height={areaY}
              fill="transparent"
              onMouseEnter={() => setAtivo(i)}
            />
          ))}
        </svg>
      )}

      {ativo !== null && largura > 0 && (
        <div
          className="pointer-events-none absolute z-10 rounded-[--radius-controle] border border-borda bg-superficie px-3 py-2 shadow-md"
          style={{
            left: x(ativo),
            top: 4,
            transform:
              ativo > rotulos.length / 2
                ? 'translateX(calc(-100% - 14px))'
                : 'translateX(14px)',
          }}
        >
          <p className="text-[11px] font-semibold text-texto">
            semana de {rotulos[ativo]}
          </p>
          <ul className="mt-1.5 space-y-1">
            {series.map((s) => (
              <li
                key={s.rotulo}
                className="flex items-center gap-2 text-[11px] whitespace-nowrap text-texto-suave"
              >
                <span
                  className="inline-block h-2 w-2 shrink-0 rounded-full"
                  style={{ background: s.cor }}
                  aria-hidden
                />
                {s.rotulo}
                <strong className="ml-auto pl-4 text-xs tabular-nums text-texto">
                  {s.valores[ativo]}
                </strong>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// --------------------------------------------------------------------------
// Sparkline
// --------------------------------------------------------------------------

/**
 * Faísca de tendência. Também em pixel real: esticada por viewBox, a
 * espessura do traço distorce junto e o desenho sai borrado.
 */
export function Sparkline({
  valores,
  cor,
  maximo,
  altura = 40,
}: {
  valores: number[]
  cor: string
  maximo: number
  altura?: number
}) {
  const [caixa, largura] = useLargura<HTMLDivElement>()
  const id = useId()

  const P = 3
  const x = (i: number) => (i * (largura - P * 2)) / Math.max(1, valores.length - 1) + P
  const y = (v: number) => altura - P - (v / Math.max(1, maximo)) * (altura - P * 2)
  const d = suave(valores, x, y)

  return (
    <div ref={caixa} className="w-full">
      {largura > 0 && (
        <svg width={largura} height={altura} aria-hidden>
          <defs>
            <linearGradient id={`${id}-s`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={cor} stopOpacity="0.20" />
              <stop offset="100%" stopColor={cor} stopOpacity="0" />
            </linearGradient>
          </defs>
          <path
            d={`${d} L ${x(valores.length - 1)} ${altura} L ${x(0)} ${altura} Z`}
            fill={`url(#${id}-s)`}
          />
          <path
            d={d}
            fill="none"
            stroke={cor}
            strokeWidth={1.75}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
          <circle
            cx={x(valores.length - 1)}
            cy={y(valores[valores.length - 1])}
            r={2.75}
            fill={cor}
          />
        </svg>
      )}
    </div>
  )
}

// --------------------------------------------------------------------------
// Barras comparadas
// --------------------------------------------------------------------------

/**
 * Previsto contra medido, uma dupla de barras por ordem de correção.
 *
 * As duas dividem a mesma escala: é a comparação entre elas que é a
 * informação inteira deste gráfico.
 */
export function BarrasComparadas({
  itens,
}: {
  itens: { rotulo: string; previsto: number; medido: number; acertou: boolean }[]
}) {
  const maximo = Math.max(1, ...itens.flatMap((i) => [i.previsto, i.medido]))

  // A entrada cresce a partir do zero na primeira pintura: ver as duas
  // barras partindo da mesma origem é o que torna a comparação legível de
  // imediato.
  const [pronto, setPronto] = useState(false)
  useEffect(() => {
    const t = requestAnimationFrame(() => setPronto(true))
    return () => cancelAnimationFrame(t)
  }, [])

  return (
    <ul className="divide-y divide-borda">
      {itens.map((item, i) => (
        <li key={item.rotulo + i} className="py-4 first:pt-0 last:pb-0">
          <div className="flex items-start justify-between gap-4">
            <p className="text-sm leading-snug text-texto">{item.rotulo}</p>
            <span
              className={[
                'shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold whitespace-nowrap',
                item.acertou ? 'bg-sucesso/10 text-sucesso' : 'bg-alerta/10 text-alerta',
              ].join(' ')}
            >
              {/* Ícone + palavra: o estado nunca é comunicado só por cor. */}
              {item.acertou ? '✓ causa extinta' : '⚠ hipótese descartada'}
            </span>
          </div>

          <div className="mt-3 space-y-2">
            {(
              [
                ['previsto', item.previsto, 'var(--serie-1)'],
                ['medido', item.medido, 'var(--serie-2)'],
              ] as const
            ).map(([nome, valor, cor]) => (
              <div key={nome} className="flex items-center gap-3">
                <span className="w-14 shrink-0 text-[11px] text-texto-suave">{nome}</span>
                <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-superficie-alt">
                  <div
                    className="h-full rounded-full transition-[width] duration-700 ease-out"
                    style={{
                      width: pronto ? `${(valor / maximo) * 100}%` : '0%',
                      background: cor,
                    }}
                  />
                </div>
                <strong className="w-8 shrink-0 text-right text-sm tabular-nums text-texto">
                  {valor}
                </strong>
              </div>
            ))}
          </div>
        </li>
      ))}
    </ul>
  )
}

// --------------------------------------------------------------------------
// Barra empilhada
// --------------------------------------------------------------------------

/** Composição de um todo: uma barra, partes rotuladas, sem donut. */
export function BarraEmpilhada({
  partes,
}: {
  partes: { rotulo: string; valor: number; cor: string }[]
}) {
  const total = partes.reduce((s, p) => s + p.valor, 0) || 1

  return (
    <div>
      <div className="flex h-3 w-full gap-[3px]" role="img">
        {partes.map((p) => (
          <div
            key={p.rotulo}
            className="rounded-full"
            style={{ width: `${(p.valor / total) * 100}%`, background: p.cor }}
            title={`${p.rotulo}: ${p.valor}`}
          />
        ))}
      </div>
      <dl className="mt-4 grid gap-4 sm:grid-cols-3">
        {partes.map((p) => (
          <div key={p.rotulo} className="flex items-start gap-2.5">
            <span
              className="mt-[9px] inline-block h-2 w-2 shrink-0 rounded-full"
              style={{ background: p.cor }}
              aria-hidden
            />
            <div className="min-w-0">
              <dd className="text-xl font-bold tabular-nums text-texto">
                {Math.round((p.valor / total) * 100)}%
                <span className="ml-1.5 text-xs font-normal text-texto-suave">
                  {p.valor} casos
                </span>
              </dd>
              <dt className="mt-0.5 text-xs text-texto-suave">{p.rotulo}</dt>
            </div>
          </div>
        ))}
      </dl>
    </div>
  )
}
