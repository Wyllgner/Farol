export type Fonte = {
  documento: string
  dono: string
}

export type Balao = {
  id: string
  direcao: 'entrada' | 'saida'
  texto: string
  fontes?: Fonte[]
  hora: string
  /** Só faz sentido em mensagens enviadas, como no WhatsApp real. */
  entregue?: boolean
}

export type EventoServidor =
  | { tipo: 'digitando' }
  | {
      tipo: 'mensagem'
      direcao: 'saida'
      texto: string
      acoes_rapidas: string[]
      fontes: Fonte[]
    }

export function agora(): string {
  return new Date().toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** O motor usa *asterisco* para negrito, como o próprio WhatsApp. */
export function comNegrito(texto: string): string {
  return texto.replace(/\*(.+?)\*/g, '<strong>$1</strong>')
}
