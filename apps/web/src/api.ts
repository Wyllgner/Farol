/**
 * Cliente HTTP das superfícies restritas.
 *
 * O token do administrador vive só no navegador de quem o digitou: ele
 * nunca é embutido no bundle (variável de build viraria segredo público
 * dentro do JavaScript entregue a todo mundo) e nunca aparece na URL —
 * query string entra no histórico do navegador e no log do proxy.
 *
 * `sessionStorage`, e não `localStorage`, de propósito: o acesso morre
 * quando a aba fecha. Se a apresentação acontecer em uma máquina
 * emprestada, o token não fica lá depois.
 */

const CHAVE = 'farol.token'
export const CABECALHO_TOKEN = 'X-Farol-Token'

export function obterToken(): string {
  return sessionStorage.getItem(CHAVE) ?? ''
}

export function guardarToken(token: string): void {
  sessionStorage.setItem(CHAVE, token.trim())
}

export function esquecerToken(): void {
  sessionStorage.removeItem(CHAVE)
}

/** Erro de autorização, separado dos demais para a tela poder pedir o token de novo. */
export class NaoAutorizado extends Error {
  constructor() {
    super('Token ausente ou inválido.')
  }
}

export async function apiRestrita(caminho: string, init: RequestInit = {}): Promise<Response> {
  const token = obterToken()
  const cabecalhos = new Headers(init.headers)
  if (token) cabecalhos.set(CABECALHO_TOKEN, token)

  const resposta = await fetch(caminho, { ...init, headers: cabecalhos })

  // 401 invalida o token guardado na hora: manter um token morto em
  // memória só produz uma sequência de falhas silenciosas mais adiante.
  if (resposta.status === 401) {
    esquecerToken()
    throw new NaoAutorizado()
  }
  return resposta
}

export async function jsonRestrito<T>(caminho: string, init: RequestInit = {}): Promise<T> {
  const resposta = await apiRestrita(caminho, init)
  if (!resposta.ok) throw new Error(`${resposta.status}`)
  return (await resposta.json()) as T
}
