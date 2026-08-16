import { useCallback, useEffect, useState } from 'react'

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
  /** Troca o participante das superfícies do participante. */
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
    porque: 'orientar não é acompanhar — e ele sabe a hora de parar',
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
      fetch('/api/demo/estado').then((r) => r.json()),
      fetch('/api/demo/cenarios').then((r) => r.json()),
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
      const r = await fetch(`/api/demo/${caminho}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: corpo ? JSON.stringify(corpo) : undefined,
      })
      if (!r.ok) throw new Error()
      const dados = await r.json()
      setAviso(mensagem ?? JSON.stringify(dados))
      await carregar()
    } catch {
      setAviso('Não consegui concluir a ação.')
    } finally {
      setOcupado(false)
    }
  }

  return (
    <div className="space-y-8">
      <header>
        <p className="text-xs font-medium tracking-widest text-dourado-600 uppercase">
          Apresentação
        </p>
        <h2 className="text-2xl font-semibold text-marinho-900">
          Console de Demonstração
        </h2>
        <p className="mt-1 max-w-2xl text-sm text-neutro-600">
          Os botões chamam exatamente as mesmas funções que o agendador
          chamaria. O que se demonstra aqui é o que roda em produção.
        </p>
      </header>

      {aviso && (
        <p
          role="status"
          className="rounded-[--radius-suave] bg-neutro-100 p-3 font-mono text-xs break-all text-neutro-900"
        >
          {aviso}
        </p>
      )}

      <section>
        <h3 className="text-sm font-semibold tracking-wide text-neutro-600 uppercase">
          Controles
        </h3>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Botao
            disabled={ocupado}
            onClick={() =>
              acao('disparar-gatilhos', undefined, 'Gatilhos disparados.')
            }
          >
            Disparar gatilhos
          </Botao>

          <span className="inline-flex items-center gap-1">
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
              className="min-h-[44px] w-20 rounded-[--radius-suave] border border-neutro-300 px-2 text-base"
            />
            <Botao
              disabled={ocupado}
              onClick={() =>
                acao('avancar-tempo', { dias }, `Avançou ${dias} dia(s).`)
              }
            >
              Avançar tempo
            </Botao>
          </span>

          <Botao
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
            disabled={ocupado}
            onClick={() =>
              acao('restaurar-saldos', undefined, 'Orçamento de atenção restaurado.')
            }
          >
            Restaurar orçamento
          </Botao>

          <Botao
            disabled={ocupado}
            tom="alerta"
            onClick={() => acao('resetar', undefined, 'Mundo recriado do zero.')}
          >
            Resetar tudo
          </Botao>
        </div>
        <p className="mt-2 text-xs text-neutro-600">
          Avançar o tempo também executa os laços que vencerem no caminho —
          deixar o relógio andar sem verificar produziria um estado que nunca
          existiria de verdade.
        </p>
      </section>

      <section>
        <h3 className="text-sm font-semibold tracking-wide text-neutro-600 uppercase">
          Trocar participante
        </h3>
        <ul className="mt-3 grid gap-2 sm:grid-cols-2">
          {cenarios.map((c) => (
            <li key={c.telefone}>
              <button
                onClick={() => {
                  aoEscolherParticipante(c.telefone)
                  setAviso(`Participante: ${c.nome}`)
                }}
                aria-current={c.telefone === handleAtual ? 'true' : undefined}
                className={[
                  'w-full rounded-[--radius-suave] border p-3 text-left',
                  c.telefone === handleAtual
                    ? 'border-marinho-500 bg-marinho-50'
                    : 'border-neutro-300 bg-white',
                ].join(' ')}
              >
                <p className="text-xs font-semibold text-marinho-700 uppercase">
                  {c.rotulo}
                </p>
                <p className="mt-0.5 text-neutro-900">{c.nome}</p>
                <p className="text-xs text-neutro-600">{c.detalhe}</p>
              </button>
            </li>
          ))}
        </ul>
      </section>

      {estado && (
        <section>
          <h3 className="text-sm font-semibold tracking-wide text-neutro-600 uppercase">
            Estado do mundo
          </h3>
          <dl className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {Object.entries(estado)
              .filter(([, v]) => typeof v === 'number')
              .map(([chave, valor]) => (
                <div
                  key={chave}
                  className="rounded-[--radius-suave] border border-neutro-300 bg-white p-3"
                >
                  <dt className="text-xs text-neutro-600">
                    {chave.replaceAll('_', ' ')}
                  </dt>
                  <dd className="text-2xl font-semibold text-marinho-900">
                    {String(valor)}
                  </dd>
                </div>
              ))}
          </dl>
        </section>
      )}

      <section>
        <h3 className="text-sm font-semibold tracking-wide text-neutro-600 uppercase">
          Roteiro de 6 minutos
        </h3>
        <ol className="mt-3 space-y-2">
          {ROTEIRO.map((r, i) => (
            <li
              key={r.passo}
              className="flex gap-3 rounded-[--radius-suave] border border-neutro-300 bg-white p-3"
            >
              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-marinho-700 text-sm text-white">
                {i + 1}
              </span>
              <div>
                <p className="font-medium text-marinho-900">{r.passo}</p>
                <p className="text-sm text-neutro-900">{r.acao}</p>
                <p className="text-xs text-neutro-600 italic">{r.porque}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}

function Botao({
  children,
  onClick,
  disabled,
  tom,
}: {
  children: React.ReactNode
  onClick: () => void
  disabled?: boolean
  tom?: 'alerta'
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={[
        'rounded-[--radius-suave] px-4 text-sm font-medium disabled:opacity-40',
        tom === 'alerta'
          ? 'border border-dourado-600 text-dourado-600'
          : 'bg-marinho-700 text-white',
      ].join(' ')}
    >
      {children}
    </button>
  )
}
