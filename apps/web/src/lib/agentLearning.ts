import type { ProductSkill } from './api'

export type SkillFamily = { key: string; label: string; records: ProductSkill[] }

export function skillFamilyKeyFromRef(ref: string) {
  const id = ref.replace(/^skill:/, '').replace(/@\d+$/, '')
  const tail = id.split('.').at(-1) ?? id
  return tail.replaceAll('_', '').toLowerCase()
}

export function groupSkillFamilies(skills: ProductSkill[]): SkillFamily[] {
  const groups = new Map<string, ProductSkill[]>()
  for (const skill of skills) {
    const tail = skill.skill_id.split('.').at(-1) ?? skill.skill_id
    const key = tail.replaceAll('_', '').toLowerCase()
    groups.set(key, [...(groups.get(key) ?? []), skill])
  }
  return [...groups.entries()].map(([key, records]) => ({
    key,
    label: preferredSkillLabel(records),
    records: [...records].sort((a, b) => statusRank(b.status) - statusRank(a.status)),
  })).sort((a, b) => a.label.localeCompare(b.label))
}

function preferredSkillLabel(records: ProductSkill[]) {
  const canonical = records.find((item) => /[A-Z]/.test(item.skill_id.split('.').at(-1) ?? '')) ?? records[0]
  return canonical?.skill_id.split('.').at(-1) ?? 'Skill'
}

function statusRank(status: string) {
  return ({ active: 5, validated: 4, candidate: 3, superseded: 2, deprecated: 1 } as Record<string, number>)[status] ?? 0
}
