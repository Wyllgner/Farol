/**
 * Paleta das séries de gráfico.
 *
 * Vive fora de Graficos.tsx porque não é componente: misturar constantes
 * e componentes no mesmo módulo quebra o fast refresh do Vite.
 *
 * Os quatro tons foram validados como paleta categórica: faixa de
 * luminosidade, piso de croma, separação sob deuteranopia, protanopia e
 * tritanopia (pior par 14.3 ΔE) e contraste ≥ 3:1 contra a superfície.
 * Trocar um tom no olho quebra essa garantia em silêncio.
 */

export const CORES = [
  'var(--serie-1)',
  'var(--serie-2)',
  'var(--serie-3)',
  'var(--serie-4)',
] as const

export const COR_RESTO = 'var(--serie-resto)'

/**
 * Cor da série pela posição fixa.
 *
 * A cor segue a entidade, nunca o ranking: se ela mudasse com a ordem,
 * filtrar uma série repintaria as outras e a leitura da semana passada
 * deixaria de valer. "outras" é o resto, não uma quinta série, e por
 * isso é cinza.
 */
export function corDaSerie(indice: number, rotulo?: string): string {
  if (rotulo === 'outras') return COR_RESTO
  return CORES[indice] ?? COR_RESTO
}
