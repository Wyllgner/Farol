import { useState } from 'react'
import { guardarToken, obterToken } from '../api'
import { Botao, Campo, Cartao, ESTILO_ENTRADA } from './Ui'

/**
 * Porta das superfícies restritas: Console de Demonstração e Como decide.
 *
 * Ela não decide nada sozinha — quem autoriza é o servidor, a cada
 * requisição. Este componente existe para não mostrar uma tela quebrada a
 * quem não tem acesso, e para dar um lugar onde digitar o token uma vez
 * por sessão. Esconder no front nunca é a proteção; a proteção é o 401.
 */
export default function PortaoRestrito({
  titulo,
  children,
}: {
  titulo: string
  children: React.ReactNode
}) {
  const [token, setToken] = useState(obterToken())
  const [digitado, setDigitado] = useState('')

  if (token) return <>{children}</>

  return (
    <div className="mx-auto max-w-lg py-10">
      <Cartao>
        <div className="space-y-4 p-6">
          <div>
            <h2 className="text-lg font-semibold text-azul-titulo">{titulo}</h2>
            <p className="mt-1 text-sm text-texto-suave">
              Superfície restrita. Esta tela altera o estado do sistema e não fica
              aberta ao público.
            </p>
          </div>

          <form
            onSubmit={(evento) => {
              evento.preventDefault()
              const limpo = digitado.trim()
              if (!limpo) return
              guardarToken(limpo)
              setToken(limpo)
            }}
            className="space-y-3"
          >
            <Campo
              id="token"
              rotulo="Token de acesso"
              ajuda="Fica guardado só nesta aba e é esquecido quando ela fecha."
            >
              <input
                id="token"
                type="password"
                autoComplete="off"
                value={digitado}
                onChange={(evento) => setDigitado(evento.target.value)}
                className={`${ESTILO_ENTRADA} h-11`}
                placeholder="••••••••••••"
              />
            </Campo>
            <Botao type="submit" className="h-11 w-full">
              Entrar
            </Botao>
          </form>
        </div>
      </Cartao>
    </div>
  )
}
