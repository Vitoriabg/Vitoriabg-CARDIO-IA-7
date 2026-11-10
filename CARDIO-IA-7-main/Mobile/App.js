import React, { useEffect, useState } from 'react'
import { ActivityIndicator, Pressable, RefreshControl, SafeAreaView, ScrollView, StatusBar, StyleSheet, Text, TextInput, View } from 'react-native'

const CONFIG_URL = process.env.EXPO_PUBLIC_CONFIG_URL
async function getConfig() {
  if (!CONFIG_URL) throw new Error('Configure EXPO_PUBLIC_CONFIG_URL para acessar o endereço público da API.')
  const response = await fetch(CONFIG_URL, { cache: 'no-store' })
  if (!response.ok) throw new Error('Não foi possível carregar a configuração pública.')
  const value = await response.json()
  if (!value.api_base_url) throw new Error('O endereço da API ainda não foi configurado.')
  return value.api_base_url.replace(/\/$/, '')
}
async function request(path, token, options = {}) {
  const base = await getConfig()
  const response = await fetch(`${base}/api/v1${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers } })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body?.error?.message || 'Não foi possível concluir a solicitação.')
  return body
}
const date = value => value ? new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) : 'Aguardando leitura'

export default function App() {
  const [token, setToken] = useState('')
  const [username, setUsername] = useState('demo')
  const [password, setPassword] = useState('')
  const [caseId, setCaseId] = useState('')
  const [cases, setCases] = useState([])
  const [dashboard, setDashboard] = useState(null)
  const [history, setHistory] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [analysis, setAnalysis] = useState(false)
  const login = async () => {
    setLoading(true); setError('')
    try {
      const result = await request('/auth/login', null, { method: 'POST', body: JSON.stringify({ username, password }) })
      setToken(result.access_token)
      const data = await request('/cases?limit=100', result.access_token)
      setCases(data.items || [])
      if (data.items?.[0]) setCaseId(data.items[0].case_id)
      else setError('Nenhum caso está vinculado a esta conta.')
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }
  const refresh = async () => {
    if (!token || !caseId) return
    setRefreshing(true)
    try {
      const [nextDashboard, nextHistory] = await Promise.all([request(`/cases/${caseId}/dashboard`, token), request(`/cases/${caseId}/measurements?limit=20`, token)])
      setDashboard(nextDashboard); setHistory(nextHistory.items || []); setError('')
    } catch (e) { setError(e.message) } finally { setRefreshing(false) }
  }
  useEffect(() => { if (token && caseId) { refresh(); const timer = setInterval(refresh, 3000); return () => clearInterval(timer) } }, [token, caseId])
  const analyze = async () => {
    if (!dashboard?.measurement || dashboard.prediction?.status !== 'ready' || analysis) return
    setAnalysis(true); setError('Solicitação de análise enviada ao processamento.')
    try {
      await request(`/cases/${caseId}/analyses`, token, { method: 'POST', body: JSON.stringify({ measurement_id: dashboard.measurement.measurement_id, context_revision: dashboard.context.context_revision }) })
      await refresh()
    } catch (e) { setError(e.message) } finally { setAnalysis(false) }
  }
  const signOut = () => { setToken(''); setDashboard(null); setCases([]); setCaseId(''); setPassword('') }
  if (!token) return <SafeAreaView style={styles.safe}><StatusBar barStyle="dark-content"/><ScrollView contentContainerStyle={styles.login}><View style={styles.logo}><Text style={styles.logoHeart}>♥</Text></View><Text style={styles.kicker}>MONITORAMENTO CARDÍACO</Text><Text style={styles.title}>Coração sob controle.</Text><Text style={styles.sub}>Entre para acompanhar os indicadores do seu caso simulado.</Text><Text style={styles.label}>Usuário</Text><TextInput style={styles.input} autoCapitalize="none" value={username} onChangeText={setUsername} autoComplete="username"/><Text style={styles.label}>Senha</Text><TextInput style={styles.input} secureTextEntry value={password} onChangeText={setPassword} autoComplete="current-password"/><Pressable style={styles.button} onPress={login} disabled={loading}><Text style={styles.buttonText}>{loading ? 'Entrando…' : 'Entrar no painel'}</Text></Pressable>{error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}<Text style={styles.disclaimer}>Ambiente acadêmico com dados sintéticos. Não é ferramenta clínica.</Text></ScrollView></SafeAreaView>
  return <SafeAreaView style={styles.safe}><StatusBar barStyle="dark-content"/><ScrollView contentContainerStyle={styles.container} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh}/> }><View style={styles.header}><View><Text style={styles.kicker}>CARDIOIA · AO VIVO</Text><Text style={styles.title}>Visão geral</Text></View><Pressable onPress={signOut} accessibilityRole="button"><Text style={styles.signout}>Sair</Text></Pressable></View><View style={styles.greeting}><Text style={styles.greetingTitle}>Olá, {username}</Text><Text style={styles.sub}>Acompanhamento do caso simulado</Text></View>{cases.length > 1 && <View style={styles.caseRow}><Text style={styles.label}>Caso ativo</Text>{cases.map(item => <Pressable key={item.case_id} onPress={()=>setCaseId(item.case_id)} style={[styles.caseChip, caseId===item.case_id && styles.caseChipActive]}><Text style={[styles.caseText, caseId===item.case_id && styles.caseTextActive]}>{item.title || item.case_id}</Text></Pressable>)}</View>}{error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}<View style={styles.metricRow}><View style={styles.metric}><Text style={styles.metricLabel}>BATIMENTOS</Text><Text style={styles.metricValue}>{dashboard?.measurement?.bpm ?? '—'}<Text style={styles.unit}> bpm</Text></Text><Text style={styles.metricNote}>{date(dashboard?.measurement?.received_at)}</Text></View><View style={styles.metric}><Text style={styles.metricLabel}>TEMPERATURA</Text><Text style={styles.metricValue}>{dashboard?.measurement?.temperatura ?? '—'}<Text style={styles.unit}> °C</Text></Text><Text style={styles.metricNote}>Sensor IoT simulado</Text></View></View><View style={styles.panel}><Text style={styles.kicker}>PREVISÃO DO MODELO</Text><Text style={[styles.risk, dashboard?.prediction?.classificacao_risco === 'alto' ? styles.high : styles.low]}>{dashboard?.prediction?.status === 'ready' ? (dashboard.prediction.classificacao_risco === 'alto' ? 'Atenção elevada' : 'Faixa baixa') : dashboard?.prediction?.status === 'missing_context' ? 'Contexto pendente' : dashboard?.prediction?.status === 'out_of_domain' ? 'Fora do domínio' : 'Aguardando dados'}</Text><Text style={styles.metricNote}>{dashboard?.prediction?.probabilidade != null ? `${Math.round(dashboard.prediction.probabilidade * 100)}% score do modelo` : dashboard?.prediction?.reason || 'Score indisponível'}</Text>{dashboard?.analysis?.recommendation && <Text style={styles.body}>Análise concluída · {date(dashboard.analysis.completed_at)}</Text>}<Pressable onPress={analyze} disabled={!dashboard?.measurement || dashboard?.prediction?.status !== 'ready' || analysis} style={[styles.button, styles.secondaryButton]}><Text style={styles.secondaryText}>{analysis ? 'Enviando…' : 'Solicitar análise'}</Text></Pressable></View><View style={styles.panel}><View style={styles.sectionHeader}><Text style={styles.sectionTitle}>Últimas medições</Text><Text style={styles.metricNote}>{history.length} registros</Text></View>{history.slice(0,6).map(item=><View key={item.measurement_id} style={styles.historyRow}><View><Text style={styles.historyValue}>{item.bpm} bpm · {item.temperatura} °C</Text><Text style={styles.metricNote}>{date(item.received_at)}</Text></View><Text style={styles.received}>Recebida</Text></View>)}{!history.length && <Text style={styles.body}>As medições aparecerão aqui quando o dispositivo enviar dados.</Text>}</View><View style={styles.disclaimerBox}><Text style={styles.disclaimer}>Resultados simulados para fins acadêmicos. Não constituem diagnóstico, prescrição ou recomendação clínica.</Text></View></ScrollView></SafeAreaView>
}

const styles = StyleSheet.create({ safe: { flex: 1, backgroundColor: '#f5f7f5' }, container: { padding: 20, paddingBottom: 42 }, login: { flexGrow: 1, justifyContent: 'center', padding: 28 }, logo: { width: 52, height: 52, borderRadius: 17, backgroundColor: '#dff1eb', alignItems: 'center', justifyContent: 'center', marginBottom: 26 }, logoHeart: { color: '#197a68', fontSize: 24 }, kicker: { color: '#87958f', fontSize: 10, letterSpacing: 1.4, fontWeight: '700' }, title: { color: '#172b29', fontSize: 29, lineHeight: 36, fontWeight: '800', marginTop: 8 }, sub: { color: '#76837f', fontSize: 13, lineHeight: 20, marginTop: 7 }, label: { color: '#50605a', fontSize: 11, fontWeight: '700', marginTop: 20, marginBottom: 7 }, input: { backgroundColor: '#fff', height: 46, borderColor: '#dfe7e2', borderWidth: 1, borderRadius: 9, paddingHorizontal: 12, color: '#172b29' }, button: { minHeight: 46, borderRadius: 9, backgroundColor: '#197a68', alignItems: 'center', justifyContent: 'center', marginTop: 22 }, buttonText: { color: '#fff', fontSize: 13, fontWeight: '700' }, error: { color: '#a84e46', backgroundColor: '#fbefed', padding: 11, borderRadius: 8, fontSize: 11, marginTop: 14 }, disclaimer: { color: '#87938d', fontSize: 10, lineHeight: 16, marginTop: 26 }, header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }, greeting: { marginTop: 29, marginBottom: 18 }, greetingTitle: { color: '#172b29', fontSize: 23, fontWeight: '800' }, signout: { color: '#4c7569', fontSize: 12, fontWeight: '700', padding: 10 }, metricRow: { flexDirection: 'row', gap: 10, marginBottom: 12 }, metric: { flex: 1, backgroundColor: '#fff', borderWidth: 1, borderColor: '#e7ece8', borderRadius: 12, padding: 15, minHeight: 108 }, metricLabel: { color: '#87938e', fontSize: 9, letterSpacing: 1, fontWeight: '700' }, metricValue: { color: '#203330', fontSize: 25, fontWeight: '800', marginTop: 11 }, unit: { color: '#81908a', fontSize: 11, fontWeight: '500' }, metricNote: { color: '#84918b', fontSize: 10, marginTop: 6 }, panel: { backgroundColor: '#fff', borderColor: '#e7ece8', borderWidth: 1, borderRadius: 12, padding: 16, marginBottom: 12 }, risk: { alignSelf: 'flex-start', overflow: 'hidden', borderRadius: 18, paddingVertical: 7, paddingHorizontal: 11, marginTop: 13, fontSize: 11, fontWeight: '700' }, high: { color: '#b64c43', backgroundColor: '#fbebe9' }, low: { color: '#317963', backgroundColor: '#e8f4ee' }, body: { color: '#76837f', fontSize: 11, lineHeight: 17, marginTop: 12 }, secondaryButton: { backgroundColor: '#f3f8f5', borderColor: '#d8e6df', borderWidth: 1 }, secondaryText: { color: '#2e7666', fontSize: 12, fontWeight: '700' }, sectionHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 9 }, sectionTitle: { color: '#172b29', fontSize: 14, fontWeight: '700' }, historyRow: { paddingVertical: 11, borderTopColor: '#eef1ef', borderTopWidth: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }, historyValue: { color: '#34443f', fontSize: 12, fontWeight: '700' }, received: { color: '#508272', fontSize: 10 }, disclaimerBox: { backgroundColor: '#eef4f0', borderRadius: 9, padding: 12 }, caseRow: { marginBottom: 14 }, caseChip: { alignSelf: 'flex-start', borderColor: '#d9e5df', borderWidth: 1, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8, marginTop: 7, backgroundColor: '#fff' }, caseChipActive: { backgroundColor: '#e7f3ef', borderColor: '#a9cdbf' }, caseText: { color: '#586861', fontSize: 11 }, caseTextActive: { color: '#176e5f', fontWeight: '700' } })
