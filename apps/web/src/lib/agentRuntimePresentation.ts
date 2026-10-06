export const rolePresentation: Record<string, { alias: string; cn: string; tone: string; copy: string; copyEn: string }> = {
  DecisionRole: { alias: 'ORACLE', cn: '判谕者', tone: 'cyan', copy: '证据进入收束阶段后，ORACLE 生成 Decision，并保留引用、冲突与未决项。', copyEn: 'ORACLE closes verified context into a Decision while preserving citations, conflicts, and unknowns.' },
  InvestigationRole: { alias: 'ARGUS', cn: '百眼调查者', tone: 'violet', copy: 'ARGUS 围绕 EvidenceNeed 推进持久 Case，选择 Skill 与 Capability；需要补证时委派 Enrichment。', copyEn: 'ARGUS advances a durable Case around EvidenceNeed, selects Skill and Capability, and delegates Enrichment when required.' },
  EnrichmentRole: { alias: 'ALCHEMIST', cn: '炼证者', tone: 'amber', copy: 'ALCHEMIST 接收 Enrichment 子任务，把缺失维度补成新的 Evidence 与 Knowledge。', copyEn: 'ALCHEMIST receives Enrichment child tasks and turns missing dimensions into new Evidence and Knowledge.' },
}

export const activeStatuses = new Set(['submitted', 'queued', 'running', 'waiting_input', 'waiting_dependency'])
