import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import useSWR from 'swr'
import { Activity, AlertCircle, ArrowDownRight, ArrowUpRight, Bell, Check, ChevronDown, CircleHelp, Clock3, HeartPulse, LogOut, MessageCircle, RefreshCw, Send, ShieldCheck, Sparkles, Thermometer, Wind } from 'lucide-react'
import './styles.css'

const readConfig = async () => {
  try {
    const response = await fetch('/runtime-config.json', { cache: 'no-store' })
    if (response.ok) return response.json()
  } catch {}
  return { api_base_url: import.meta.env.VITE_API_BASE_URL || '' }
}
const configPromise = readConfig()
const api = async (path, { token, ...options } = {}) => {
  const config = await configPromise
  const base = (config.api_base_url || '').replace(/\/$/, '')
  if (!base) throw new Error('API não configurada. Defina o endereço em public/runtime-config.json.')
  const response = await fetch(`${base}/api/v1${path}`, {
    ...options,
    headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  })
  const result = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(result?.error?.message || 'Não foi possível concluir a solicitação.')
  return result
}
const fetcher = ([path, token]) => api(path, { token })
const formatDate = (value) => value ? new Intl.DateTimeFormat('pt-BR', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'Aguardando leitura'

function Login({ onLogin }) {
  const [username, setUsername] = useState('demo')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (event) => {
    event.preventDefault(); setError(''); setBusy(true)
    try { const result = await api('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }); onLogin(result.access_token, username) }
    catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  return <main className="login-shell"><section className="login-panel"><div className="brand-mark"><HeartPulse size={22} /></div><div className="eyebrow">PLATAFORMA DE MONITORAMENTO</div><h1>Coração sob<br/><span>controle.</span></h1><p className="login-copy">Acompanhe sinais simulados e recomendações em um só lugar.</p><div className="login-note"><ShieldCheck size={17}/><span>Ambiente acadêmico com dados sintéticos</span></div></section><section className="login-form-wrap"><form className="login-form" onSubmit={submit}><div className="eyebrow">BEM-VINDO DE VOLTA</div><h2>Entre na sua conta</h2><p>Acesse seu painel CardioIA.</p><label htmlFor="username">Usuário</label><input id="username" autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)} required/><label htmlFor="password">Senha</label><input id="password" type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} required/><button className="primary-button login-submit" disabled={busy}>{busy ? 'Entrando…' : 'Entrar no painel'}<ArrowUpRight size={17}/></button>{error && <div className="error-message" role="alert"><AlertCircle size={16}/>{error}</div>}<p className="login-footnote">Seus dados de sessão permanecem apenas nesta aba.</p></form></section></main>
}

function TrendChart({ items }) {
  const points = useMemo(() => {
    const values = [...(items || [])].reverse().slice(-12).map(item => Number(item.bpm)).filter(Number.isFinite)
    if (!values.length) return ''
    const min = Math.min(...values, 50) - 5, max = Math.max(...values, 100) + 5
    return values.map((v, i) => `${values.length === 1 ? 50 : 10 + (i * 80) / (values.length - 1)},${88 - ((v - min) / (max - min || 1)) * 70}`).join(' ')
  }, [items])
  return <svg className="trend-chart" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Tendência das últimas leituras de batimentos"><defs><linearGradient id="fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#2a9d82" stopOpacity=".18"/><stop offset="1" stopColor="#2a9d82" stopOpacity="0"/></linearGradient></defs><path d="M0 25H100M0 50H100M0 75H100" className="chart-grid"/>{points && <><polygon points={`10,100 ${points} 90,100`} fill="url(#fill)"/><polyline points={points} className="chart-line"/></>}</svg>
}

function Dashboard({ token, username, onLogout }) {
  const [caseId, setCaseId] = useState('')
  const [notice, setNotice] = useState('')
  const [chatOpen, setChatOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [conversationId, setConversationId] = useState('')
  const [messageId, setMessageId] = useState('')
  const [analysisId, setAnalysisId] = useState('')
  const { data: casesData, error: casesError } = useSWR(['/cases?limit=100', token], fetcher)
  const cases = casesData?.items || []
  const selectedCase = caseId || cases[0]?.case_id || ''
  const { data: dashboard, error, isLoading, mutate } = useSWR(selectedCase ? [`/cases/${selectedCase}/dashboard`, token] : null, fetcher, { refreshInterval: 3000, revalidateOnFocus: true })
  const { data: history } = useSWR(selectedCase ? [`/cases/${selectedCase}/measurements?limit=20`, token] : null, fetcher, { refreshInterval: 10000 })
  const { data: job } = useSWR(analysisId ? [`/analyses/${analysisId}`, token] : null, fetcher, { refreshInterval: 1800, refreshWhenHidden: false })
  const { data: chatResult } = useSWR(conversationId && messageId ? [`/conversations/${conversationId}/messages/${messageId}`, token] : null, fetcher, { refreshInterval: 1800, refreshWhenHidden: false })
  useEffect(() => { if (job?.status === 'completed') { setNotice('Análise concluída.'); setAnalysisId(''); mutate() } else if (job?.status === 'failed') { setNotice(job.error?.message || 'A análise falhou.'); setAnalysisId('') } }, [job, mutate])
  useEffect(() => { if (chatResult?.status === 'completed') setMessageId('') }, [chatResult])
  const measurement = dashboard?.measurement
  const prediction = dashboard?.prediction
  const recommendation = dashboard?.analysis?.recommendation
  const requestAnalysis = async () => {
    if (!measurement || prediction?.status !== 'ready') return
    try { const result = await api(`/cases/${selectedCase}/analyses`, { token, method: 'POST', body: JSON.stringify({ measurement_id: measurement.measurement_id, context_revision: dashboard.context.context_revision }) }); setAnalysisId(result.analysis_id); setNotice('Análise solicitada ao motor de IA.') }
    catch (e) { setNotice(e.message) }
  }
  const sendMessage = async (event) => {
    event.preventDefault(); if (!message.trim() || messageId) return
    try {
      let current = conversationId
      if (!current) { const created = await api('/conversations', { token, method: 'POST', body: JSON.stringify({ case_id: selectedCase }) }); current = created.conversation_id; setConversationId(current) }
      const result = await api(`/conversations/${current}/messages`, { token, method: 'POST', body: JSON.stringify({ text: message.trim() }) }); setMessage(''); setMessageId(result.message_id)
    } catch (e) { setNotice(e.message) }
  }
  const predictionLabel = prediction?.status === 'ready' ? (prediction.classificacao_risco === 'alto' ? 'Atenção elevada' : 'Faixa baixa') : prediction?.status === 'missing_context' ? 'Contexto pendente' : prediction?.status === 'out_of_domain' ? 'Fora do domínio' : 'Aguardando dados'
  return <div className="app-shell"><aside className="sidebar"><a className="brand" href="#inicio"><span className="brand-mark small"><HeartPulse size={18}/></span><span>cardio<span className="brand-strong">ia</span></span></a><div className="workspace-label">ESPAÇO DE TRABALHO</div><nav aria-label="Navegação principal"><a className="nav-link active" href="#painel"><Activity size={17}/>Visão geral</a><a className="nav-link" href="#sinais"><HeartPulse size={17}/>Sinais cardíacos</a><button className="nav-link" onClick={()=>setChatOpen(!chatOpen)}><MessageCircle size={17}/>Assistente IA</button></nav><div className="sidebar-bottom"><div className="system-card"><div className="system-dot"/><div><strong>Sistema conectado</strong><span>Atualização automática</span></div></div><button className="profile" onClick={onLogout}><span className="avatar">{username.slice(0,1).toUpperCase()}</span><span className="profile-info"><strong>{username}</strong><small>Sair da conta</small></span><LogOut size={16}/></button></div></aside>
    <main className="main-area"><header className="topbar"><div><div className="eyebrow">MONITORAMENTO CARDÍACO</div><h1>Visão geral</h1></div><div className="top-actions"><span className="sync-pill"><span className="live-dot"/>Ao vivo</span><button className="icon-button" aria-label="Atualizar dados" onClick={()=>mutate()}><RefreshCw size={17}/></button><span className="date-label">{new Intl.DateTimeFormat('pt-BR',{weekday:'short',day:'numeric',month:'short'}).format(new Date())}</span></div></header>
    <div className="content"><div className="greeting-row"><div><h2>Olá, {username} <span className="wave">—</span></h2><p>Acompanhe os indicadores do caso simulado.</p></div><label className="case-select-label">Caso ativo<select value={selectedCase} onChange={e=>setCaseId(e.target.value)} aria-label="Selecionar caso">{cases.map(c=><option key={c.case_id} value={c.case_id}>{c.title || c.case_id}</option>)}</select><ChevronDown className="select-chevron" size={15}/></label></div>
    {(casesError || error) && <div className="error-banner" role="alert"><AlertCircle size={17}/>{(casesError || error).message}<button onClick={()=>mutate()}>Tentar novamente</button></div>}
    {notice && <div className="notice-banner" role="status"><Check size={16}/>{notice}<button aria-label="Fechar aviso" onClick={()=>setNotice('')}>×</button></div>}
    {isLoading && !dashboard ? <div className="loading-state">Carregando dados do caso…</div> : !cases.length && !casesError ? <div className="empty-state"><HeartPulse size={24}/><h3>Nenhum caso disponível</h3><p>Não encontramos casos vinculados a esta conta.</p></div> : <>
      <section className="vitals-grid" aria-label="Indicadores atuais"><article className="vital-card"><div className="card-label"><span>Batimentos</span><span className="vital-icon red"><HeartPulse size={17}/></span></div><div className="vital-value">{measurement?.bpm ?? '—'}<small>{measurement ? 'bpm' : 'sem leitura'}</small></div><div className="vital-foot"><span className="metric-status"><span className="mini-dot red-dot"/>{measurement ? 'Última leitura recebida' : 'Aguardando dispositivo'}</span><ArrowUpRight size={14}/></div></article><article className="vital-card"><div className="card-label"><span>Temperatura</span><span className="vital-icon amber"><Thermometer size={17}/></span></div><div className="vital-value">{measurement?.temperatura ?? '—'}<small>{measurement ? '°C' : 'sem leitura'}</small></div><div className="vital-foot"><span className="metric-status"><span className="mini-dot amber-dot"/>{measurement ? 'Sensor de temperatura' : 'Aguardando dispositivo'}</span><ArrowDownRight size={14}/></div></article><article className="vital-card risk-card"><div className="card-label"><span>Risco preditivo</span><span className="vital-icon teal"><Activity size={17}/></span></div><div className="risk-value"><span className={`risk-badge ${prediction?.classificacao_risco === 'alto' ? 'risk-high' : prediction?.status === 'ready' ? 'risk-low' : 'risk-neutral'}`}>{predictionLabel}</span></div><div className="vital-foot"><span className="metric-status">{prediction?.probabilidade != null ? `${Math.round(prediction.probabilidade * 100)}% score do modelo` : prediction?.reason || 'Sem previsão disponível'}</span></div></article></section>
      <section className="main-grid"><article className="panel chart-panel" id="sinais"><div className="panel-heading"><div><span className="eyebrow">SINAIS RECENTES</span><h3>Frequência cardíaca</h3></div><span className="period-tag">Últimas medições</span></div><div className="chart-reading"><strong>{measurement?.bpm ?? '—'}</strong><span>bpm</span><span className="chart-time"><Clock3 size={13}/>{formatDate(measurement?.received_at)}</span></div><div className="chart-wrap"><div className="chart-y-labels"><span>150</span><span>120</span><span>90</span><span>60</span></div><TrendChart items={history?.items}/></div><div className="chart-legend"><span><i/>Frequência cardíaca</span><span>{history?.items?.length || 0} leituras no histórico</span></div></article>
      <article className="panel recommendation-panel"><div className="panel-heading"><div><span className="eyebrow">ANÁLISE INTELIGENTE</span><h3>Recomendações</h3></div><span className="ai-mark"><Sparkles size={15}/></span></div>{recommendation ? <><div className="recommendation-status"><span className="risk-badge risk-low">{recommendation.classificacao_risco === 'alto' ? 'Risco alto' : 'Análise concluída'}</span><small>{formatDate(dashboard?.analysis?.completed_at)}</small></div><p className="recommendation-copy">Recomendações geradas para a medição <code>{dashboard?.analysis?.measurement_id?.slice(0,14)}</code>.</p><ul className="recommendation-list">{(recommendation.acoes_operacionais || recommendation.protocolos_sugeridos || []).slice(0,3).map((item,i)=><li key={i}><Check size={15}/><span>{typeof item === 'string' ? item : item.nome || item.acao || JSON.stringify(item)}</span></li>)}</ul></> : <div className="recommendation-empty"><div className="sparkle-orb"><Sparkles size={20}/></div><strong>{analysisId ? 'Análise em processamento' : 'Ainda sem recomendação'}</strong><p>Uma análise usa os sinais disponíveis e o contexto sintético.</p><button className="secondary-button" disabled={!measurement || prediction?.status !== 'ready' || !!analysisId} onClick={requestAnalysis}>{analysisId ? 'Processando…' : 'Solicitar análise'}<ArrowUpRight size={15}/></button></div>}<div className="academic-note"><CircleHelp size={15}/><span>Resultados simulados para fins acadêmicos. Não são diagnóstico ou orientação clínica.</span></div></article></section>
      <section className="panel measurement-panel"><div className="panel-heading"><div><span className="eyebrow">ATIVIDADE DO DISPOSITIVO</span><h3>Últimas medições</h3></div><span className="history-count">{history?.items?.length || 0} registros</span></div><div className="measurement-table-wrap"><table><thead><tr><th>Recebida em</th><th>Batimentos</th><th>Temperatura</th><th>Origem</th><th>Estado</th></tr></thead><tbody>{(history?.items || []).slice(0,5).map(item=><tr key={item.measurement_id}><td>{formatDate(item.received_at)}</td><td><strong>{item.bpm} bpm</strong></td><td>{item.temperatura} °C</td><td>{item.historical ? 'Sincronizada' : 'Dispositivo IoT'}</td><td><span className="table-status"><span className="mini-dot teal-dot"/>Recebida</span></td></tr>)}{!history?.items?.length && <tr><td colSpan="5" className="table-empty">As medições aparecerão aqui quando o dispositivo enviar dados.</td></tr>}</tbody></table></div></section>
      </>}
      <footer className="page-footer"><span>CardioIA · Fase 7</span><span><Wind size={14}/>Dados sintéticos · {formatDate(measurement?.received_at)}</span></footer>
    </div></main>
    {chatOpen && <aside className="chat-drawer" aria-label="Assistente CardioIA"><div className="chat-head"><div><span className="eyebrow">ASSISTENTE</span><h3>Conversa CardioIA</h3></div><button className="icon-button" aria-label="Fechar conversa" onClick={()=>setChatOpen(false)}>×</button></div><div className="chat-messages"><div className="chat-intro"><span className="ai-mark"><Sparkles size={16}/></span><p>Faça perguntas sobre este caso simulado. As respostas são geradas pelo motor local.</p></div>{chatResult?.status === 'completed' && <div className="chat-reply">{chatResult.response || chatResult.answer || chatResult.text || 'Resposta recebida.'}</div>}{messageId && <p className="chat-pending">Preparando resposta…</p>}</div><form className="chat-compose" onSubmit={sendMessage}><label className="sr-only" htmlFor="chat-input">Sua mensagem</label><textarea id="chat-input" value={message} onChange={e=>setMessage(e.target.value)} maxLength={2000} placeholder="Escreva sua pergunta…"/><button className="primary-button" aria-label="Enviar mensagem" disabled={!message.trim() || !!messageId}><Send size={16}/></button></form></aside>}
  </div>
}

function App() {
  const [session, setSession] = useState(null)
  const [ready, setReady] = useState(false)
  useEffect(() => { const saved = sessionStorage.getItem('cardioia-session'); if (saved) { try { setSession(JSON.parse(saved)) } catch { sessionStorage.removeItem('cardioia-session') } } setReady(true) }, [])
  const login = (token, username) => { const value = { token, username }; sessionStorage.setItem('cardioia-session', JSON.stringify(value)); setSession(value) }
  const logout = () => { sessionStorage.removeItem('cardioia-session'); setSession(null) }
  if (!ready) return <main className="boot-screen">CardioIA</main>
  return session ? <Dashboard token={session.token} username={session.username} onLogout={logout}/> : <Login onLogin={login}/>
}

createRoot(document.getElementById('root')).render(<App />)
