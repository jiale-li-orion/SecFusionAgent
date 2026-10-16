import type { IncidentSummary, IncidentTimelineEvent } from './api/intelligence'
import type { WorldIncidentCandidate, WorldStory } from './api/world'
export type LibraryMoment = { id: string; title: string; summary: string | null; timestamp: string | null; basis: 'reported_date' | 'record_updated' | 'published' | 'observed' | 'unknown'; incident?: IncidentSummary; candidate?: WorldIncidentCandidate }
export function validLibraryTime(value: string | null | undefined): string | null { return value && Number.isFinite(Date.parse(value)) ? value : null }
export function libraryDay(value: string | null): string { return value ? new Date(value).toISOString().slice(0, 10) : 'unknown' }
export function groupLibraryMoments(incidents: IncidentSummary[], candidates: WorldIncidentCandidate[]) {
  const retained = new Set(incidents.map(item => item.candidate_id))
  const moments: LibraryMoment[] = incidents.map(incident => ({ id: `incident:${incident.incident_id}`, title: typeof incident.watch_state?.title === 'string' ? incident.watch_state?.title : incident.current_summary || incident.incident_type.replaceAll('_', ' '), summary: typeof incident.watch_state?.title === 'string' ? incident.current_summary : null, timestamp: validLibraryTime(typeof incident.watch_state?.timeline_start === 'string' ? incident.watch_state?.timeline_start : incident.updated_at), basis: typeof incident.watch_state?.timeline_start === 'string' ? 'reported_date' : validLibraryTime(incident.updated_at) ? 'record_updated' : 'unknown', incident }))
  candidates.filter(item => !retained.has(item.candidate_id)).forEach(candidate => {
    const published = validLibraryTime(candidate.published_at), observed = validLibraryTime(candidate.observed_at)
    moments.push({ id: `candidate:${candidate.candidate_id}`, title: candidate.headline, summary: candidate.summary, timestamp: published ?? observed, basis: published ? 'published' : observed ? 'observed' : 'unknown', candidate })
  })
  const groups = new Map<string, LibraryMoment[]>()
  moments.sort((a, b) => (a.timestamp ? Date.parse(a.timestamp) : -Infinity) - (b.timestamp ? Date.parse(b.timestamp) : -Infinity) || a.id.localeCompare(b.id)).forEach(item => { const day = libraryDay(item.timestamp); groups.set(day, [...(groups.get(day) ?? []), item]) })
  return [...groups].map(([day, items]) => ({ day, items }))
}
export function orderIncidentHistory(events: IncidentTimelineEvent[]) {
  return [...events].sort((a, b) => { const time = (event: IncidentTimelineEvent) => Date.parse(validLibraryTime(event.event_time) ?? validLibraryTime(event.observed_at) ?? '') || 0; return time(a) - time(b) || a.event_id.localeCompare(b.event_id) })
}
export function materialLibraryDate(story: Pick<WorldStory, 'published_date' | 'published_at' | 'observed_at'>) {
  const day = story.published_date
  // A source calendar date has no time zone; retain it verbatim after validation.
  if (day && /^\d{4}-\d{2}-\d{2}$/.test(day) && validLibraryTime(day) && new Date(day).toISOString().slice(0, 10) === day) return { value: day, published: true, dateOnly: true }
  const published = validLibraryTime(story.published_at)
  return { value: published ?? validLibraryTime(story.observed_at), published: Boolean(published), dateOnly: false }
}

// Deterministic lexical similarity over the loaded sample, owned by frontend presentation.
// This does not persist classifications or claim embedding-based semantic analysis.
const themes = [
  { id: 'ai', zh: '模型与智能体', en: 'Models & agents', terms: ['agent', 'model', 'llm', '模型', '智能体', '人工智能'] },
  { id: 'vulnerability', zh: '漏洞与利用', en: 'Vulnerabilities & exploits', terms: ['cve', 'vulnerability', 'exploit', '漏洞', '利用', '补丁'] },
  { id: 'supply-chain', zh: '软件供应链', en: 'Software supply chain', terms: ['dependency', 'package', 'repository', '供应链', '依赖', '软件包', '仓库'] },
  { id: 'identity', zh: '身份与数据', en: 'Identity & data', terms: ['credential', 'authentication', 'privacy', '身份', '认证', '隐私', '泄露', '凭证'] },
  { id: 'infrastructure', zh: '网络与基础设施', en: 'Networks & infrastructure', terms: ['network', 'cloud', 'kubernetes', 'firewall', '网络', '基础设施', '服务器'] },
  { id: 'governance', zh: '治理与标准', en: 'Governance & standards', terms: ['standard', 'compliance', 'regulation', 'governance', 'policy', '标准', '合规', '监管', '治理', '政策'] },
] as const
const aliases = [
  { token: 'generative-ai', zh: '生成式 AI', en: 'Generative AI', forms: ['generative ai', 'generative artificial intelligence', '生成式人工智能', '人工智能生成'] },
  { token: 'prompt-injection', zh: '提示注入', en: 'Prompt injection', forms: ['prompt injection', '提示注入'] },
  { token: 'supply-chain', zh: '供应链安全', en: 'Supply chain', forms: ['supply chain', '供应链'] },
  { token: 'llm', zh: '语言模型', en: 'Language models', forms: ['large language model', '大语言模型', '语言模型', 'llm'] },
  { token: 'agent', zh: '智能体', en: 'Agents', forms: ['智能体', 'agent'] },
  { token: 'vulnerability', zh: '漏洞研究', en: 'Vulnerabilities', forms: ['vulnerability', 'vulnerabilities', '漏洞'] },
  { token: 'credential', zh: '身份凭证', en: 'Credentials', forms: ['credential', '凭证'] },
  { token: 'privacy', zh: '隐私保护', en: 'Privacy', forms: ['privacy', '隐私'] },
  { token: 'ransomware', zh: '勒索软件', en: 'Ransomware', forms: ['ransomware', '勒索软件'] },
]
const stopWords = new Set('a an and are as at be been being by can could for from has have how in into is it its of on or our that the their these this through to using via was we were will with without you your new security cybersecurity research study report approach framework based towards toward learning systems system analysis'.split(' '))
const chineseStopWords = new Set(['我们', '通过', '以及', '一个', '一种', '进行', '基于', '研究', '安全', '方法', '系统', '分析', '技术', '提出', '可以', '实现', '本文'])
export type MaterialCluster = { id: string; zh: string; en: string; items: WorldStory[]; terms: string[] }
function containsTerm(content: string, term: string) { return /^[a-z\s-]+$/.test(term) ? new RegExp(`\\b${term}s?\\b`, 'i').test(content) : content.includes(term) }
function contentTokens(value: string) {
  const content = value.toLowerCase().slice(0, 12000)
  const tokens = (content.match(/[a-z][a-z0-9-]{2,}/g) ?? []).map(word => word.endsWith('s') && word.length > 4 ? word.slice(0, -1) : word).filter(word => !stopWords.has(word))
  // Character bigrams handle Chinese without a dependency or a browser-specific tokenizer.
  for (const span of content.match(/[\u3400-\u9fff]+/g) ?? []) {
    for (let i = 0; i < span.length - 1; i++) { const token = span.slice(i, i + 2); if (!chineseStopWords.has(token)) tokens.push(token) }
  }
  for (const alias of aliases) if (alias.forms.some(form => containsTerm(content, form))) tokens.push(alias.token, alias.token)
  return tokens
}
export function clusterLibraryMaterials(stories: WorldStory[]): MaterialCluster[] {
  const unique = [...new Map(stories.filter(story => story.object_id || story.incident_id).map(story => [story.story_id, story])).values()]
  if (!unique.length) return []
  const documents = unique.map(story => {
    const counts = new Map<string, number>()
    for (const token of [...contentTokens(story.headline), ...contentTokens(story.headline), ...contentTokens(story.excerpt ?? '')]) counts.set(token, (counts.get(token) ?? 0) + 1)
    return counts
  })
  const frequency = new Map<string, number>()
  documents.forEach(document => document.forEach((_, token) => frequency.set(token, (frequency.get(token) ?? 0) + 1)))
  const vectors = documents.map(document => {
    const vector = new Map<string, number>()
    document.forEach((count, token) => vector.set(token, (1 + Math.log(count)) * (1 + Math.log((unique.length + 1) / ((frequency.get(token) ?? 0) + 1)))))
    const norm = Math.sqrt([...vector.values()].reduce((sum, weight) => sum + weight * weight, 0)) || 1
    vector.forEach((weight, token) => vector.set(token, weight / norm))
    return vector
  })
  const similarity = vectors.map(a => vectors.map(b => [...a].reduce((sum, [token, weight]) => sum + weight * (b.get(token) ?? 0), 0)))
  const groups = unique.map((_, index) => [index])
  // Average-link agglomeration avoids treating a single shared topic word as an entire category.
  while (groups.length > 1) {
    let best = .12, left = -1, right = -1
    for (let a = 0; a < groups.length; a++) for (let b = a + 1; b < groups.length; b++) {
      const score = groups[a].reduce((sum, i) => sum + groups[b].reduce((subtotal, j) => subtotal + similarity[i][j], 0), 0) / (groups[a].length * groups[b].length)
      if (score > best) { best = score; left = a; right = b }
    }
    if (left < 0) break
    groups[left].push(...groups[right]); groups.splice(right, 1)
  }
  return groups.map(indices => {
    const items = indices.map(index => unique[index])
    const common = [...frequency.keys()].map(token => ({ token, count: indices.filter(index => documents[index].has(token)).length, weight: indices.reduce((sum, index) => sum + (vectors[index].get(token) ?? 0), 0) })).filter(term => term.count >= Math.min(2, indices.length)).sort((a, b) => b.count - a.count || b.weight - a.weight || a.token.localeCompare(b.token))
    const terms = common.slice(0, 5).map(term => term.token)
    const alias = aliases.find(item => terms.includes(item.token))
    const content = items.map(item => `${item.headline} ${item.excerpt ?? ''}`).join(' ').toLowerCase()
    const rankedThemes = themes.map(theme => ({ theme, count: theme.terms.filter(term => containsTerm(content, term)).length })).sort((a, b) => b.count - a.count)
    const theme = rankedThemes[0]?.count ? rankedThemes[0].theme : null
    const fallback = items[0].headline.length > 44 ? `${items[0].headline.slice(0, 44)}…` : items[0].headline
    return { id: `cluster:${[...items.map(item => item.story_id)].sort().join('|')}`, zh: alias?.zh ?? theme?.zh ?? fallback, en: alias?.en ?? theme?.en ?? fallback, items, terms }
  }).sort((a, b) => b.items.length - a.items.length)
}
