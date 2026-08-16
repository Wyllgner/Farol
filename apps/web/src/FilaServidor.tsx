import { useCallback, useEffect, useState } from 'react'
import {
  Botao,
  CabecalhoConteudo,
  Cartao,
  Etiqueta,
  ESTILO_ENTRADA,
  TituloSecao,
  Vazio,
} from './componentes/Ui'

type Caso = {
  id: string
  categoria: string
  canal: string
  sensivel: boolean
  situacao: string
  score_consequencia: number
  orientacao_padrao_falhou: boolean
  contrato_resolucao: string
  resumo: string
  criado_em: string
  minutos_esperando: number
  assumido_por: string | null
  dossie: Record<string, unknown> | null
  rascunho_resposta: string | null
}

type Metricas = {
  na_fila: number
  encerrados: number
  com_orientacao_padrao_falha: number
  sensiveis: number
}

const SERVIDOR = 'Servidora Ana (SECOEAD)'

export default function FilaServidor() {
  const [casos, setCasos] = useState<Caso[]>([])
  const [metricas, setMetricas] = useState<Metricas | null>(null)
  const [selecionado, setSelecionado] = useState<string | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  const carregar = useCallback(async () => {
    try {
      const [f, m] = await Promise.all([
        fetch('/api/fila').then((r) => r.json()),
        fetch('/api/fila/metricas').then((r) => r.json()),
      ])
      setCasos(f)
      setMetricas(m)
      setErro(null)
    } catch {
      setErro('Não consegui carregar a fila.')
    }
  }, [])

  useEffect(() => {
    carregar()
  }, [carregar])

  const caso = casos.find((c) => c.id === selecionado) ?? null

  return (
    <div className="space-y-6">
      <CabecalhoConteudo
        chapeu="Equipe · SECOEAD"
        titulo="Fila do Servidor"
        descricao="Ordenada pela consequência de não atender, não por ordem de chegada. Nada sai em nome da instituição sem sua revisão."
        acao={
          <Botao tom="secundario" onClick={carregar}>
            Atualizar
          </Botao>
        }
      />

      {metricas && (
        <dl className="grid gap-3 sm:grid-cols-4">
          <Indicador rotulo="Na fila" valor={metricas.na_fila} destaque />
          <Indicador
            rotulo="Orientação falhou"
            valor={metricas.com_orientacao_padrao_falha}
          />
          <Indicador rotulo="Sensíveis" valor={metricas.sensiveis} />
          <Indicador rotulo="Encerrados" valor={metricas.encerrados} />
        </dl>
      )}

      <div className="grid gap-6 xl:grid-cols-[24rem_1fr]">
        <section aria-label="Casos">
          <TituloSecao nivel={3}>Casos abertos</TituloSecao>

          {erro && <p className="mt-3 text-sm text-erro">{erro}</p>}

          <ul className="mt-3 space-y-2">
            {casos.length === 0 && !erro && (
              <li>
                <Vazio>
                  Nada na fila. Sucesso, aqui, é este número ser baixo.
                </Vazio>
              </li>
            )}

            {casos.map((c) => (
              <li key={c.id}>
                <button
                  onClick={() => setSelecionado(c.id)}
                  aria-current={c.id === selecionado ? 'true' : undefined}
                  className={[
                    'w-full rounded-[--radius-card] border p-4 text-left transition-colors',
                    c.id === selecionado
                      ? 'border-azul bg-azul-100'
                      : 'border-borda bg-superficie hover:bg-superficie-alt',
                  ].join(' ')}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-xs font-bold tracking-wider text-azul-titulo uppercase">
                      {c.categoria}
                    </span>
                    <span className="shrink-0 rounded-full bg-azul px-2 py-0.5 text-xs font-semibold text-sobre-azul">
                      {c.score_consequencia.toFixed(1)}
                    </span>
                  </div>

                  <p className="mt-1.5 text-sm text-texto">{c.resumo}</p>

                  <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                    <Etiqueta>{c.canal}</Etiqueta>
                    <Etiqueta>{c.minutos_esperando} min</Etiqueta>
                    {c.sensivel && <Etiqueta tom="alerta">sensível</Etiqueta>}
                    {c.orientacao_padrao_falhou && (
                      <Etiqueta tom="alerta">orientação falhou</Etiqueta>
                    )}
                    {c.assumido_por && (
                      <Etiqueta tom="azul">{c.assumido_por}</Etiqueta>
                    )}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </section>

        {caso ? (
          <DetalheCaso caso={caso} aoMudar={carregar} />
        ) : (
          <Vazio>Selecione um caso para ver o dossiê completo.</Vazio>
        )}
      </div>
    </div>
  )
}

function DetalheCaso({ caso, aoMudar }: { caso: Caso; aoMudar: () => void }) {
  const [texto, setTexto] = useState(caso.rascunho_resposta ?? '')
  const [titulo, setTitulo] = useState('')
  const [aviso, setAviso] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState(false)

  useEffect(() => {
    setTexto(caso.rascunho_resposta ?? '')
    setTitulo('')
    setAviso(null)
  }, [caso.id, caso.rascunho_resposta])

  async function acao(caminho: string, corpo: object, mensagem: string) {
    setOcupado(true)
    try {
      const r = await fetch(`/api/fila/${caso.id}/${caminho}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(corpo),
      })
      if (!r.ok) throw new Error(await r.text())
      setAviso(mensagem)
      aoMudar()
    } catch {
      setAviso('Não consegui concluir a ação.')
    } finally {
      setOcupado(false)
    }
  }

  const dossie = caso.dossie ?? {}
  const encerrado = caso.situacao === 'encerrado'

  return (
    <Cartao>
      {/* Crítico no topo: o dossiê tem de ser lido em 10 segundos. */}
      <p className="text-xs font-bold tracking-[0.16em] text-texto-suave uppercase">
        {caso.categoria} · {caso.canal}
      </p>
      <h2 className="mt-1 text-xl font-bold">{caso.resumo}</h2>
      <div className="mt-3 h-0.5 w-20 bg-ciano" aria-hidden />

      {caso.orientacao_padrao_falhou && (
        <p className="mt-4 rounded-[--radius-controle] border-l-4 border-alerta bg-alerta/5 p-3 text-sm">
          A orientação padrão já foi entregue e <strong>não resolveu</strong> para
          esta pessoa. Responder o mesmo de novo não vai adiantar.
        </p>
      )}

      <dl className="mt-4 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        <Campo rotulo="Motivo do encaminhamento" valor={dossie.motivo_do_escalonamento} />
        <Campo rotulo="Nível de identidade" valor={dossie.nivel_identidade} />
        <Campo rotulo="Confiança" valor={String(dossie.confianca ?? '—')} />
        <Campo rotulo="Espera" valor={`${caso.minutos_esperando} min`} />
      </dl>

      <details className="mt-4 rounded-[--radius-controle] border border-borda p-3">
        <summary className="cursor-pointer text-sm font-semibold text-azul-titulo">
          Dossiê completo
        </summary>
        <pre className="mt-3 max-h-80 overflow-auto rounded bg-superficie-alt p-3 text-xs">
          {JSON.stringify(caso.dossie, null, 2)}
        </pre>
      </details>

      <div className="mt-6">
        <label htmlFor="resposta" className="text-sm font-semibold text-azul-titulo">
          Resposta ao participante
        </label>
        <p className="mb-1 text-xs text-texto-suave">
          Rascunho sugerido. Edite à vontade — nada sai sem sua revisão.
        </p>
        <textarea
          id="resposta"
          rows={6}
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          disabled={encerrado}
          className={`${ESTILO_ENTRADA} py-2 disabled:bg-superficie-alt`}
        />
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {!caso.assumido_por && !encerrado && (
          <Botao
            tom="secundario"
            disabled={ocupado}
            onClick={() => acao('assumir', { servidor: SERVIDOR }, 'Caso assumido.')}
          >
            Assumir
          </Botao>
        )}

        <Botao
          disabled={ocupado || encerrado || !texto.trim()}
          onClick={() =>
            acao(
              'responder',
              { servidor: SERVIDOR, texto },
              'Resposta enviada e caso encerrado.',
            )
          }
        >
          Revisar e enviar
        </Botao>
      </div>

      <div className="mt-6 border-t border-borda pt-4">
        <TituloSecao nivel={3}>Aprovar como conhecimento</TituloSecao>
        <p className="mt-2 text-xs text-texto-suave">
          A resposta entra na base, passa a ser citável como fonte, e casos
          semelhantes deixam de escalar.
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          <label htmlFor="titulo" className="sr-only">
            Título do documento
          </label>
          <input
            id="titulo"
            value={titulo}
            onChange={(e) => setTitulo(e.target.value)}
            placeholder="Título do documento"
            className={`${ESTILO_ENTRADA} flex-1`}
          />
          <Botao
            tom="secundario"
            disabled={ocupado || titulo.trim().length < 3 || !texto.trim()}
            onClick={() =>
              acao(
                'aprovar-conhecimento',
                { servidor: SERVIDOR, titulo, conteudo: texto },
                'Conhecimento aprovado e já indexado.',
              )
            }
          >
            Aprovar
          </Botao>
        </div>
      </div>

      {aviso && (
        <p role="status" className="mt-4 text-sm font-medium text-sucesso">
          {aviso}
        </p>
      )}
    </Cartao>
  )
}

function Indicador({
  rotulo,
  valor,
  destaque,
}: {
  rotulo: string
  valor: number
  destaque?: boolean
}) {
  return (
    <div
      className={[
        'rounded-[--radius-card] border p-4',
        destaque ? 'border-azul bg-azul-100' : 'border-borda bg-superficie',
      ].join(' ')}
    >
      <dt className="text-xs text-texto-suave">{rotulo}</dt>
      <dd className="text-3xl font-bold text-azul-titulo">{valor}</dd>
    </div>
  )
}

function Campo({ rotulo, valor }: { rotulo: string; valor: unknown }) {
  return (
    <>
      <dt className="text-texto-suave">{rotulo}</dt>
      <dd className="text-texto">{String(valor ?? '—')}</dd>
    </>
  )
}
