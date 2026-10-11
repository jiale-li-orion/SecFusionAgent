export const networkGroups = [
  { id: 'risk', label: '风险与漏洞', color: '#ce5265', kinds: ['vulnerability', 'weakness', 'exploitartifact', 'incident', 'vulnerability_type', 'cve_collection'] },
  { id: 'software', label: '项目与产品', color: '#4263eb', kinds: ['repo', 'repository', 'product', 'package', 'softwareversion', 'project', 'open_source_project', 'open_source_project_collection', 'model', 'tool', 'tool_type', 'deployment_scope'] },
  { id: 'change', label: '开发与修复', color: '#138e83', kinds: ['commit', 'release', 'pullrequest', 'issue', 'release_channel', 'incidentevent'] },
  { id: 'research', label: '研究与资料', color: '#8d62c4', kinds: ['document', 'researchwork', 'normativedocument', 'benchmark', 'research_phase', 'validation_method', 'report_subset', 'web_resource', 'evidence', 'claim'] },
  { id: 'other', label: '其他关联', color: '#74879c', kinds: [] },
]
export function networkGroup(kind: string) {
  return networkGroups.find(group => group.kinds.includes(kind.toLowerCase())) ?? networkGroups[4]
}
export function networkDate(value: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '时间未记录'
}
