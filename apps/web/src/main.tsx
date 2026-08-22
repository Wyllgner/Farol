import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Sem StrictMode de proposito. Ele monta cada componente duas vezes em
// desenvolvimento, e o espelho do WhatsApp abre um WebSocket na montagem:
// a primeira conexao drenava a fila de mensagens pendentes e era descartada
// no mesmo instante, e a segunda encontrava a fila vazia. A mensagem
// proativa constava como entregue no banco e nunca aparecia na tela.
createRoot(document.getElementById('root')!).render(<App />)
