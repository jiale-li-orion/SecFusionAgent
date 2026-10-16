import assert from 'node:assert/strict'
import { test } from 'node:test'
import { build } from 'esbuild'
const output = await build({ entryPoints: ['src/lib/libraryPresentation.ts'], bundle: true, format: 'esm', platform: 'node', write: false })
const { groupLibraryMoments, clusterLibraryMaterials, orderIncidentHistory, materialLibraryDate } = await import(`data:text/javascript;base64,${Buffer.from(output.outputFiles[0].text).toString('base64')}`)
test('timeline distinguishes updates, publication, observation and unknown dates; deduplicates promotion', () => {
  const groups = groupLibraryMoments([{ incident_id: 'i', candidate_id: 'retained', updated_at: '2026-10-02T00:00:00Z', incident_type: 'incident' }], [
    { candidate_id: 'retained', headline: 'duplicate', observed_at: '2026-10-01' },
    { candidate_id: 'a', headline: 'published', published_at: '2026-10-01T23:00:00-03:00', observed_at: '2026-10-03' },
    { candidate_id: 'b', headline: 'observed', published_at: 'invalid', observed_at: '2026-10-03' },
    { candidate_id: 'c', headline: 'unknown', observed_at: 'invalid' },
  ])
  assert.deepEqual(groups.map(group => group.day), ['unknown', '2026-10-02', '2026-10-03'])
  assert.equal(groups.flatMap(group => group.items).length, 4)
  assert.equal(groups[1].items[0].basis, 'record_updated'); assert.equal(groups[1].items[1].basis, 'published'); assert.equal(groups[2].items[0].basis, 'observed')
})
const story = (id, headline, excerpt = null) => ({ story_id: id, object_id: id, headline, excerpt, category: 'vendor' })
test('content similarity joins related material while unrelated material remains separate', () => {
  const groups = clusterLibraryMaterials([story('a', 'Prompt injection attacks against language model agents'), story('b', 'Defending language model agents against prompt injection'), story('c', 'Cloud firewall network configuration')])
  assert.equal(groups.length, 2)
  assert.deepEqual(new Set(groups[0].items.map(item => item.story_id)), new Set(['a', 'b']))
  assert.equal(groups[1].items[0].story_id, 'c')
})
test('Chinese content and bilingual concept aliases support grouping', () => {
  const chinese = clusterLibraryMaterials([story('a', '供应链依赖软件包恶意攻击'), story('b', '恶意软件包依赖攻击与供应链审计'), story('c', '身份凭证泄露')])
  assert.equal(chinese.length, 2)
  assert.equal(chinese[0].items.length, 2)
  const bilingual = clusterLibraryMaterials([story('a', 'Prompt injection in LLM agents'), story('b', '智能体大语言模型提示注入攻击')])
  assert.equal(bilingual.length, 1)
})
test('category labels alone cannot merge dissimilar content; duplicates and empty records are handled', () => {
  const groups = clusterLibraryMaterials([story('a', 'Thunderstorm rainfall forecast'), story('b', 'Orchestral violin performance'), story('a', 'Thunderstorm rainfall forecast'), { story_id: 'unreadable', headline: 'No object' }])
  assert.equal(groups.length, 2)
  assert.equal(groups.reduce((sum, group) => sum + group.items.length, 0), 2)
  assert.equal(clusterLibraryMaterials([]).length, 0)
  assert.equal(clusterLibraryMaterials([story('blank', '', '')]).length, 1)
})
test('history sorts by event time and does not mutate response', () => {
  const items = [{ event_id: 'late', event_time: '2026-10-03', observed_at: '2026-10-04' }, { event_id: 'early', event_time: '2026-10-01', observed_at: '2026-10-05' }]
  assert.deepEqual(orderIncidentHistory(items).map(item => item.event_id), ['early', 'late']); assert.equal(items[0].event_id, 'late')
})
test('150 loaded items remain complete, deterministic and groupable without losing independent items', () => {
  const items = Array.from({ length: 150 }, (_, i) => story(`item-${i}`, i < 75 ? 'Prompt injection attacks against language model agents' : 'Cloud firewall network configuration'))
  const groups = clusterLibraryMaterials(items)
  assert.equal(groups.length, 2)
  assert.equal(groups.reduce((sum, group) => sum + group.items.length, 0), 150)
  assert.equal(new Set(groups.flatMap(group => group.items.map(item => item.story_id))).size, 150)
  assert.deepEqual(clusterLibraryMaterials(items).map(group => group.id), groups.map(group => group.id))
})

test('source date-only publication stays a calendar date rather than becoming observation time', () => {
  assert.deepEqual(materialLibraryDate({ published_date: '2026-10-14', published_at: null, observed_at: '2026-10-15T01:00:00Z' }), { value: '2026-10-14', published: true, dateOnly: true })
  assert.deepEqual(materialLibraryDate({ published_date: '2026-02-30', published_at: null, observed_at: '2026-10-15T01:00:00Z' }), { value: '2026-10-15T01:00:00Z', published: false, dateOnly: false })
  assert.equal(materialLibraryDate({ published_date: null, published_at: '2026-10-14T23:00:00Z', observed_at: '2026-10-15' }).published, true)
})
