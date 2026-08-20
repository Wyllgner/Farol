import { useCallback, useEffect, useState } from 'react'
import { NaoAutorizado, apiRestrita, jsonRestrito } from './api'
import {
  Botao,
  CabecalhoConteudo,
  Cartao,
  ESTILO_ENTRADA,
  TituloSecao,
} from './componentes/Ui'

type Estado = {
  modo_ensaio: boolean
  participantes: number
  casos: number
  casos_na_fila: number
  casos_em_ensaio: number
  mensagens_proativas: number
  hipoteses_pendentes: number
  agrupamentos: number
  ordens_pendentes: number
  documentos: number
  categorias_liberadas: number
}

type Cenario = {
  telefone: string
  nome: string
  curso: string
  rotulo: string
  detalhe: string
}

type Props = {
  aoEscolherParticipante: (telefone: string) => void
  handleAtual: string
}

/** O roteiro de 6 minutos, na ordem que sustenta a tese. */
const ROTEIRO = [
  {
    passo: 'Antecipar',
    acao: 'Dispare os gatilhos e abra o WhatsApp',
    porque: 'a mensagem chega antes da pergunta existir',
  },
  {
    passo: 'Resolver sobre o caso da pessoa',
    acao: 'Pergunte “meu certificado já saiu?” com contato conhecido',
    porque: 'nenhum FAQ responde sobre o estado individual de alguém',
  },
  {
    passo: 'Recusar',
    acao: 'Pergunte algo fora da base',
    porque: 'sem fonte, o FAROL escala em vez de inventar',
  },
  {
    passo: 'Acompanhar',
    acao: 'Peça ajuda com 2FA e responda “Não consegui” duas vezes',
    porque: 'orientar não é acompanhar, e ele sabe a hora de parar',
  },
  {
    passo: 'Verificar se resolveu',
    acao: 'Avance 1 dia e responda “Não resolveu”',
    porque: 'ele não repete a resposta que já falhou: escala avisando',
  },
  {
    passo: 'Extinguir a causa',
    acao: 'Abra o Radar, analise e marque a ordem como implementada',
    porque: 'previsão numérica e medição em 30 dias, não palpite',
  },
]

export default function Console({ aoEscolherParticipante, handleAtual }: Props) {
  const [estado, setEstado] = useState<Estado | null>(null)
  const [cenarios, setCenarios] = useState<Cenario[]>([])
  const [ocupado, setOcupado] = useState(false)
  const [aviso, setAviso] = useState<string | null>(null)
  const [dias, setDias] = useState(1)

  const carregar = useCallback(async () => {
    const [e, c] = await Promise.all([
      jsonRestrito<Estado>('/api/demo/estado'),
      jsonRestrito<Cenario[]>('/api/demo/cenarios'),
    ])
    setEstado(e)
    setCenarios(c)
  }, [])

  useEffect(() => {
    carregar()
  }, [carregar])

  async function acao(caminho: string, corpo?: object, mensagem?: string) {
    setOcupado(true)
    setAviso(null)
    try {
      const r = await apiRestrita(`/api/demo/${caminho}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: corpo ? JSON.stringify(corpo) : undefined,
      })
      if (!r.ok) throw new Error()
      const dados = await r.json()
      setAviso(mensagem ?? JSON.stringify(dados))
      await carregar()
    } catch (erro) {
      setAviso(
        erro instanceof NaoAutorizado
          ? 'Sessão expirada. Recarregue a página e informe o token de novo.'
          : 'Não consegui concluir a ação.',
      )
    } finally {
      setOcupado(false)
    }
  }

  return (
    <div className="space-y-8">
      <CabecalhoConteudo
        chapeu="Apresentação"
        titulo="Console de Demonstração"
        descricao="Os botões chamam exatamente as mesmas funções que o agendador chamaria. O que se demonstra aqui é o que roda em produção."
      />

      {aviso && (
        <p
          role="status"
          className="rounded-[--radius-controle] bg-superficie-alt p-3 font-mono text-xs break-all text-texto"
        >
          {aviso}
        </p>
      )}

      <section>
        <TituloSecao nivel={3}>Controles</TituloSecao>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {/* Teal: tudo que é proativo/antecipação. */}
          <Botao
            tom="proativo"
            disabled={ocupado}
            onClick={() => acao('disparar-gatilhos', undefined, 'Gatilhos disparados.')}
          >
            Disparar gatilhos
          </Botao>

          <span className="inline-flex items-center gap-2">
            <label htmlFor="dias" className="sr-only">
              Dias para avançar
            </label>
            <input
              id="dias"
              type="number"
              min={1}
              max={365}
              value={dias}
              onChange={(e) => setDias(Number(e.target.value))}
              className={`${ESTILO_ENTRADA} w-20`}
            />
            <Botao
              disabled={ocupado}
              onClick={() => acao('avancar-tempo', { dias }, `Avançou ${dias} dia(s).`)}
            >
              Avançar tempo
            </Botao>
          </span>

          <Botao
            tom="secundario"
            disabled={ocupado}
            onClick={() =>
              acao(
                'modo-ensaio',
                { ativo: !estado?.modo_ensaio },
                `Modo Ensaio ${estado?.modo_ensaio ? 'desligado' : 'ligado'}.`,
              )
            }
          >
            {estado?.modo_ensaio ? 'Desligar' : 'Ligar'} Modo Ensaio
          </Botao>

          <Botao
            tom="secundario"
            disabled={ocupado}
            onClick={() =>
              acao('restaurar-saldos', undefined, 'Orçamento de atenção restaurado.')
            }
          >
            Restaurar orçamento
          </Botao>

          <Botao
            tom="perigo"
            disabled={ocupado}
            onClick={() => acao('resetar', undefined, 'Mundo recriado do zero.')}
          >
            Resetar tudo
          </Botao>
        </div>
        <p className="mt-3 text-xs text-texto-suave">
          Avançar o tempo também executa os laços que vencerem no caminho: 
          deixar o relógio andar sem verificar produziria um estado que nunca
          existiria de verdade.
        </p>
      </section>

      <section>
        <TituloSecao nivel={3}>Trocar participante</TituloSecao>
        <ul className="mt-4 grid gap-2 sm:grid-cols-2">
          {cenarios.map((c) => (
            <li key={c.telefone}>
              <button
                onClick={() => {
                  aoEscolherParticipante(c.telefone)
                  setAviso(`Participante: ${c.nome}`)
                }}
                aria-current={c.telefone === handleAtual ? 'true' : undefined}
                className={[
                  'w-full rounded-[--radius-card] border p-4 text-left transition-colors',
                  c.telefone === handleAtual
                    ? 'border-azul bg-azul-100'
                    : 'border-borda bg-superficie hover:bg-superficie-alt',
                ].join(' ')}
              >
                <p className="text-xs font-bold tracking-wider text-azul-titulo uppercase">
                  {c.rotulo}
                </p>
                <p className="mt-1 font-medium text-texto">{c.nome}</p>
                <p className="text-xs text-texto-suave">{c.detalhe}</p>
              </button>
            </li>
          ))}
        </ul>
      </section>

      {estado && (
        <section>
          <TituloSecao nivel={3}>Estado do mundo</TituloSecao>
          <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {Object.entries(estado)
              .filter(([, v]) => typeof v === 'number')
              .map(([chave, valor]) => (
                <div
                  key={chave}
                  className="rounded-[--radius-card] border border-borda bg-superficie p-3"
                >
                  <dt className="text-xs text-texto-suave">
                    {chave.replaceAll('_', ' ')}
                  </dt>
                  <dd className="text-2xl font-bold text-azul-titulo">
                    {String(valor)}
                  </dd>
                </div>
              ))}
          </dl>
        </section>
      )}

      <section>
        <TituloSecao nivel={3}>Roteiro de 6 minutos</TituloSecao>
        <ol className="mt-4 space-y-2">
          {ROTEIRO.map((r, i) => (
            <li key={r.passo}>
              <Cartao className="flex gap-4">
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-azul text-sm font-bold text-sobre-azul">
                  {i + 1}
                </span>
                <div className="min-w-0">
                  <p className="font-bold tracking-wide text-azul-titulo uppercase">
                    {r.passo}
                  </p>
                  <p className="text-sm text-texto">{r.acao}</p>
                  <p className="mt-0.5 text-xs text-texto-suave italic">{r.porque}</p>
                </div>
              </Cartao>
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}
