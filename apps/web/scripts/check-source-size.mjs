import { readdir, readFile } from 'node:fs/promises'
import { extname, join, relative } from 'node:path'

const root = new URL('../src/', import.meta.url)
const limits = [
  { prefix: 'pages/', maxLines: 700 },
  { prefix: 'components/', maxLines: 700 },
  { prefix: 'lib/api/', maxLines: 400 },
]

async function walk(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) files.push(...await walk(path))
    else if (['.ts', '.tsx'].includes(extname(entry.name))) files.push(path)
  }
  return files
}

const rootPath = root.pathname
const violations = []
for (const file of await walk(rootPath)) {
  const local = relative(rootPath, file).replaceAll('\\', '/')
  const rule = limits.find(({ prefix }) => local.startsWith(prefix))
  if (!rule) continue
  const source = await readFile(file, 'utf8')
  const lines = source.split('\n').length - 1
  if (lines > rule.maxLines) violations.push(`${local}: ${lines} lines > ${rule.maxLines}`)
}

if (violations.length) {
  console.error('Product source-size guard failed:')
  for (const violation of violations) console.error(`  ${violation}`)
  process.exit(1)
}

console.log('Product source-size guard: pages <= 700; components <= 700; API domains <= 400 lines.')
