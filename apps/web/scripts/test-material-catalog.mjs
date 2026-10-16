import assert from 'node:assert/strict'
import { test } from 'node:test'
import { build } from 'esbuild'
const output = await build({ entryPoints: ['src/lib/materialLibraryPresentation.ts'], bundle: true, format: 'esm', platform: 'node', write: false })
const { clusterMaterialPage, LIBRARY_PAGE_SIZE } = await import(`data:text/javascript;base64,${Buffer.from(output.outputFiles[0].text).toString('base64')}`)
const material = index => ({ story_id: `story-${index}`, object_id: `object-${index}`, headline: 'Prompt injection attacks against language model agents', excerpt: 'Prompt injection containment and tool sandbox research', subjects: ['prompt-injection', 'agent-safety'] })
test('clustering remains bounded to the fetched page rather than scaling with corpus size', () => {
  const result = clusterMaterialPage(Array.from({ length: 150 }, (_, index) => material(index)), [])
  assert.equal(result.reduce((sum, group) => sum + group.items.length, 0), LIBRARY_PAGE_SIZE)
  assert.equal(new Set(result.flatMap(group => group.items.map(item => item.story_id))).size, 48)
})
test('a shared granular corpus subject names the similarity cluster without changing membership', () => {
  const result = clusterMaterialPage([material(0), material(1)], [{ key: 'prompt-injection', label: '提示注入', label_en: 'Prompt injection', count: 121 }])
  assert.equal(result.length, 1)
  assert.equal(result[0].zh, '提示注入')
  assert.equal(result[0].items.length, 2)
})
