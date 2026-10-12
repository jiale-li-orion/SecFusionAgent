export function dateLabel(value: string | null | undefined, language: 'zh' | 'en') {
  if (!value || !Number.isFinite(Date.parse(value))) return '—'
  return new Date(value).toLocaleDateString(language === 'zh' ? 'zh-CN' : 'en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export function latestObservedAt(evidence: Array<{ observed_at: string }>): string | null {
  return evidence.reduce<string | null>((latest, item) => {
    const time = Date.parse(item.observed_at)
    return Number.isFinite(time) && (latest === null || time > Date.parse(latest)) ? item.observed_at : latest
  }, null)
}

export function presentationTitle(title: string) {
  // Publisher dates and link labels belong in the byline/source, not the headline.
  return title.trim().replace(/^\d{4}-\d{2}-\d{2}\s+(?=\S)/, '').replace(/\s+(?:See details|Read more)$/i, '').trim()
}
