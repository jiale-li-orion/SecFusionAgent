import assert from 'node:assert/strict'
import { test } from 'node:test'
import { build } from 'esbuild'

const compiled = await build({ entryPoints: ['src/lib/productVocabulary.ts'], bundle: true, format: 'esm', platform: 'node', write: false })
const { productTerm, skillName } = await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString('base64')}`)
const zh = (chinese) => chinese
const en = (_chinese, english) => english

test('canonical and seeded skill references share a readable bilingual name', () => {
  for (const ref of ['skill:investigation.AssessAffectedDeployment@1', 'investigation.assess_affected_deployment', 'AssessAffectedDeployment']) {
    assert.equal(skillName(ref, zh), '评估部署是否受影响')
    assert.equal(skillName(ref, en), 'Assess affected deployments')
  }
})
test('candidate, validated and active remain distinct lifecycle states', () => {
  const states = ['candidate', 'validated', 'active'].map(state => productTerm(state, zh))
  assert.equal(new Set(states).size, 3)
  assert.equal(states[0], '待验证')
  assert.ok(states.every(value => !/^[a-z_]+$/.test(value)))
})
test('unknown states remain distinguishable without implying success', () => {
  assert.equal(productTerm('waiting_for_source_review', en), 'Waiting for source review')
  assert.notEqual(productTerm('waiting_for_source_review', zh), productTerm('succeeded', zh))
})
test('public identifiers retain their exact spelling', () => {
  assert.equal(productTerm('CVE-2024-13980', zh), 'CVE-2024-13980')
})
