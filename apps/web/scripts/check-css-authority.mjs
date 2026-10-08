import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import postcss from 'postcss'

const activeStyles = ['product-foundation.css', 'product-spaces.css', 'account-space.css']
const legacyStyles = ['styles.css', 'cinematic.css', 'cinematic-seams.css', 'surface-authority.css', 'layout-authority.css']
const main = fs.readFileSync(path.resolve('src/main.tsx'), 'utf8')
const violations = []
const importedStyles = [...main.matchAll(/import\s+['"]\.\/([^'"]+\.css)['"]/g)].map(match => match[1])
if (JSON.stringify(importedStyles) !== JSON.stringify(activeStyles)) violations.push('main.tsx must load only the independent foundation, product spaces and account styles, in that order')
for (const file of legacyStyles) {
  if (main.includes(`'./${file}'`) || main.includes(`"./${file}"`)) violations.push(`main.tsx still imports the retired ${file}`)
}
for (const file of activeStyles) {
  if (!main.includes(`'./${file}'`)) violations.push(`main.tsx does not import ${file}`)
  const root = postcss.parse(fs.readFileSync(path.resolve('src', file), 'utf8'), { from: file })
  root.walkAtRules('import', rule => violations.push(`${file}:${rule.source.start.line} imports another CSS cascade`))
  root.walkDecls(decl => {
    if (!decl.important) return
    let allowed = false
    for (let parent = decl.parent; parent; parent = parent.parent) {
      if (parent.type === 'atrule' && parent.name === 'media' && parent.params.includes('prefers-reduced-motion')) allowed = true
    }
    if (!allowed) violations.push(`${file}:${decl.source.start.line} uses !important outside reduced-motion accessibility`)
  })
}
if (violations.length) {
  console.error(violations.join('\n'))
  process.exit(1)
}
console.log('CSS authority: independent foundation, product spaces and account styles; legacy cascades are not loaded; no override escalation.')
