import assert from 'node:assert/strict'
import { test } from 'node:test'
import { build } from 'esbuild'

const compiled = await build({ entryPoints: ['src/lib/taskPresentation.ts'], bundle: true, format: 'esm', platform: 'node', write: false })
const { taskAttentionGroups, taskOutcome, taskResult } = await import(`data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString('base64')}`)
const asOf = '2026-10-12T12:00:00Z'
const task = (run_id, overrides = {}) => ({ run_id, case_id: null, parent_run_id: null, predecessor_run_id: null, status: 'failed', stop_reason: 'question_reasoning_failed', updated_at: '2026-10-12T10:00:00Z', ...overrides })
const en = (_zh, english) => english

test('attention joins recorded lineage and root cause, keeping unrelated failures separate', () => {
  const groups = taskAttentionGroups([task('root'), task('child', { parent_run_id: 'root' }), task('other')], asOf)
  assert.deepEqual(groups.map(item => item.count).sort(), [1, 2])
})
test('old failures stay in history while unresolved waiting remains visible', () => {
  const groups = taskAttentionGroups([task('old', { updated_at: '2026-10-09T10:00:00Z' }), task('waiting', { status: 'waiting_dependency', updated_at: '2026-10-09T10:00:00Z' })], asOf)
  assert.deepEqual(groups.map(item => item.task.run_id), ['waiting'])
})
test('no eligible enrichment is distinct from actual execution failure', () => {
  const blocked = task('no-enrichment', { status: 'blocked', stop_reason: 'no_eligible_enrichment_operator' })
  const failed = { ...blocked, run_id: 'failed', status: 'failed' }
  assert.equal(taskOutcome(blocked, en), 'No applicable enrichment')
  assert.equal(taskOutcome(failed, en), 'Failed')
  assert.deepEqual(taskAttentionGroups([blocked, failed], asOf).map(item => item.task.run_id), ['failed'])
})
test('completed task with a saved result does not read as an unexplained failure', () => {
  const result = task('complete', { status: 'completed', result_available: true, stop_reason: 'enrichment_goal_satisfied' })
  assert.match(taskResult(result, en), /result is saved/)
})
for (const stop_reason of ['partial_evidence', 'evidence_insufficient']) {
  test(`completed ${stop_reason} keeps the evidence gap visible`, () => {
    const result = task('partial', { status: 'completed', result_available: true, stop_reason })
    assert.match(taskResult(result, en), /evidence.*(?:gaps|insufficient)/i)
    assert.doesNotMatch(taskResult(result, en), /^The result is saved\./)
  })
}
