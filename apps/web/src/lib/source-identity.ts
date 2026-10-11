type Identity = { key: string; name: string; initials: string }
const publishers: Array<Identity & { sources: string[]; hosts: string[] }> = [
  { key: 'github', name: 'GitHub', initials: 'GH', sources: ['github', 'ghsa', 'github-advisory-database', 'github-global-advisories', 'github-target-repos'], hosts: ['github.com'] },
  { key: 'arxiv', name: 'arXiv', initials: 'ar', sources: ['arxiv', 'arxiv-ai-security'], hosts: ['arxiv.org'] },
  { key: 'anthropic', name: 'Anthropic', initials: 'A', sources: ['anthropic', 'anthropic-news', 'anthropic-research', 'anthropic-system-cards'], hosts: ['anthropic.com'] },
  { key: 'huggingface', name: 'Hugging Face', initials: 'HF', sources: ['huggingface', 'hugging-face'], hosts: ['huggingface.co'] },
  { key: 'microsoft', name: 'Microsoft Security', initials: 'M', sources: ['microsoft', 'msrc', 'microsoft-security', 'microsoft-security-ai'], hosts: ['microsoft.com'] },
  { key: 'cisco', name: 'Cisco Talos', initials: 'T', sources: ['talos', 'cisco', 'cisco-talos', 'talos-research'], hosts: ['talosintelligence.com', 'cisco.com'] },
  { key: 'paloalto', name: 'Unit 42', initials: '42', sources: ['paloalto', 'palo-alto-networks', 'unit42', 'unit-42', 'unit42-research'], hosts: ['paloaltonetworks.com'] },
  { key: 'owasp', name: 'OWASP', initials: 'O', sources: ['owasp', 'owasp-genai'], hosts: ['owasp.org'] },
  { key: 'nvd', name: 'NVD', initials: 'N', sources: ['nvd', 'nvd-cves-2'], hosts: ['nvd.nist.gov', 'services.nvd.nist.gov'] },
  { key: 'nist', name: 'NIST', initials: 'NI', sources: ['nist', 'nist-ai-rmf', 'nist-genai-profile'], hosts: ['nist.gov'] },
  { key: 'cnnvd', name: 'CNNVD', initials: 'CN', sources: ['cnnvd', 'cnnvd-vulnerabilities'], hosts: ['cnnvd.org.cn'] },
  { key: 'cnvd', name: 'CNVD', initials: 'CN', sources: ['cnvd', 'cnvd-vulnerabilities'], hosts: ['cnvd.org.cn'] },
  { key: 'cisa', name: 'CISA', initials: 'C', sources: ['cisa', 'cisa-kev', 'cisa-advisories', 'cisa-cybersecurity-advisories'], hosts: ['cisa.gov'] },
  { key: 'shodan', name: 'Shodan', initials: 'S', sources: ['shodan', 'shodan-assets', 'shodan-internetdb-assets'], hosts: ['shodan.io'] },
  { key: 'openai', name: 'OpenAI', initials: 'O', sources: ['openai', 'openai-research', 'openai-safety', 'openai-deployment-safety'], hosts: ['openai.com'] },
  { key: 'nvidia', name: 'NVIDIA', initials: 'NV', sources: ['nvidia', 'nvidia-ai-red-team', 'nvidia-ai-security'], hosts: ['nvidia.com'] },
  { key: 'aws', name: 'AWS Security', initials: 'AWS', sources: ['aws', 'aws-security', 'aws-security-bulletins'], hosts: ['aws.amazon.com'] },
  { key: 'hiddenlayer', name: 'HiddenLayer', initials: 'HL', sources: ['hiddenlayer', 'hiddenlayer-reports', 'hiddenlayer-security-advisories'], hosts: ['hiddenlayer.com'] },
  { key: 'wiz', name: 'Wiz Research', initials: 'W', sources: ['wiz', 'wiz-research'], hosts: ['wiz.io'] },
  { key: 'eu', name: 'EU AI Act', initials: 'EU', sources: ['eu-ai', 'eu-ai-act', 'eu-ai-office'], hosts: ['europa.eu'] },
]

export function sourceIdentity(source?: string | null, url?: string | null): Identity {
  let domain = ''
  try { domain = new URL(url ?? '').hostname.replace(/^www\./, '') } catch { /* Source IDs also work without an external URL. */ }
  const sourceId = (source?.split(' · ')[0] ?? '').trim().toLowerCase().replace(/[\s_]+/g, '-')
  // Registered source identity takes precedence over a document's outbound URL.
  // Hostnames must match a complete domain, never a substring or URL path.
  const known = publishers.find(publisher => publisher.sources.includes(sourceId))
    ?? publishers.find(publisher => publisher.hosts.some(host => domain === host || domain.endsWith(`.${host}`)))
  if (known) return known
  const name = source?.split(' · ')[0] || domain || 'Source'
  return { key: 'other', name, initials: name.slice(0, 2).toUpperCase() }
}

/** Display-only fallback; the original canonical label is preserved in the dossier. */
export function readableObjectTitle(label: string, url?: string | null, source?: string | null) {
  const publisher = sourceIdentity(source, url).name
  const clean = label.trim()
  if (clean && !/(?:^|[:/])[0-9a-f]{24,}$/i.test(clean) && !/^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(clean)) {
    return /^(insights|news|research|blog|home)$/i.test(clean) ? `${publisher} · ${clean}` : clean
  }
  try {
    const slug = decodeURIComponent(new URL(url ?? '').pathname.split('/').filter(Boolean).at(-1) ?? '').replace(/\.(html?|pdf)$/i, '')
    if (/^[a-z][a-z0-9-]{8,}$/i.test(slug) && slug.includes('-')) return slug.replaceAll('-', ' ').replace(/^./, first => first.toUpperCase())
  } catch { /* Fall back to publisher identity. */ }
  return publisher
}
