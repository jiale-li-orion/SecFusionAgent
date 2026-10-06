import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import postcss from 'postcss'

const layoutFile = path.resolve('src/layout-authority.css')
const surfaceFile = path.resolve('src/surface-authority.css')
const cinematicFiles = [
  path.resolve('src/cinematic.css'),
  path.resolve('src/cinematic-seams.css'),
]
const visualProperties = new Set([
  'accent-color',
  'appearance',
  'box-shadow',
  'caret-color',
  'color',
  'cursor',
  'fill',
  'fill-opacity',
  'font-family',
  'font-weight',
  'letter-spacing',
  'mix-blend-mode',
  'opacity',
  'outline',
  'outline-color',
  'outline-offset',
  'outline-style',
  'outline-width',
  'scrollbar-color',
  'scrollbar-width',
  'stroke',
  'stroke-opacity',
  'stroke-width',
  'text-decoration',
  'text-decoration-color',
  'text-decoration-line',
  'text-decoration-style',
  'text-shadow',
  'text-transform',
])

function canonicalProperty(property) {
  return property.replace(/^-(?:webkit|moz|ms|o)-/, '')
}

function atRuleContext(node) {
  const context = []
  for (let parent = node.parent; parent && parent.type !== 'root'; parent = parent.parent) {
    if (parent.type === 'atrule') context.push(`@${parent.name} ${parent.params}`)
  }
  return context.reverse().join(' > ')
}

function declarationIndex(file) {
  const root = postcss.parse(fs.readFileSync(file, 'utf8'), { from: file })
  const index = new Map()
  root.walkRules((rule) => {
    const context = atRuleContext(rule)
    for (const selector of rule.selectors) {
      const key = `${context}\n${selector.trim()}`
      let properties = index.get(key)
      if (!properties) {
        properties = new Map()
        index.set(key, properties)
      }
      for (const declaration of rule.nodes.filter((node) => node.type === 'decl')) {
        properties.set(declaration.prop, { important: declaration.important })
      }
    }
  })
  return index
}

function findDeadCinematicDeclarations() {
  const authorityIndexes = [declarationIndex(surfaceFile), declarationIndex(layoutFile)]
  const violations = []

  for (const file of cinematicFiles) {
    const root = postcss.parse(fs.readFileSync(file, 'utf8'), { from: file })
    root.walkRules((rule) => {
      const context = atRuleContext(rule)
      const selectors = rule.selectors.map((selector) => selector.trim())
      for (const declaration of rule.nodes.filter((node) => node.type === 'decl')) {
        const fullyOverridden = selectors.every((selector) => authorityIndexes.some((index) => {
          const later = index.get(`${context}\n${selector}`)?.get(declaration.prop)
          return later && (!declaration.important || later.important)
        }))
        if (!fullyOverridden) continue
        violations.push({
          file,
          line: declaration.source?.start?.line ?? 0,
          property: declaration.prop,
          selector: rule.selector,
        })
      }
    })
  }
  return violations
}

function ownsVisualSemantics(property) {
  const name = canonicalProperty(property)
  return visualProperties.has(name)
    || name === 'background'
    || name.startsWith('background-')
    || name === 'border'
    || name.startsWith('border-')
    || name === 'filter'
    || name === 'backdrop-filter'
    || name === 'animation'
    || name.startsWith('animation-')
    || name === 'transition'
    || name.startsWith('transition-')
}

function ownsGeometry(property) {
  const name = canonicalProperty(property)
  return name === 'display'
    || name === 'position'
    || name === 'top'
    || name === 'right'
    || name === 'bottom'
    || name === 'left'
    || name === 'inset'
    || name.startsWith('inset-')
    || name === 'width'
    || name === 'height'
    || name.startsWith('min-width')
    || name.startsWith('max-width')
    || name.startsWith('min-height')
    || name.startsWith('max-height')
    || name === 'margin'
    || name.startsWith('margin-')
    || name === 'padding'
    || name.startsWith('padding-')
    || name === 'gap'
    || name === 'row-gap'
    || name === 'column-gap'
    || name === 'overflow'
    || name.startsWith('overflow-')
    || name === 'z-index'
    || name === 'box-sizing'
    || name === 'order'
    || name === 'transform'
    || name === 'transform-origin'
    || name === 'aspect-ratio'
    || name.startsWith('grid')
    || name.startsWith('flex')
    || name.startsWith('align-')
    || name.startsWith('justify-')
    || name.startsWith('place-')
}

function findViolations(file, predicate) {
  const root = postcss.parse(fs.readFileSync(file, 'utf8'), { from: file })
  const violations = []

  root.walkDecls((declaration) => {
    if (!predicate(declaration.prop)) return
    violations.push({
      line: declaration.source?.start?.line ?? 0,
      property: declaration.prop,
      selector: declaration.parent?.selector ?? '<at-rule>',
    })
  })

  return violations
}

const layoutViolations = findViolations(layoutFile, ownsVisualSemantics)
const surfaceViolations = findViolations(surfaceFile, ownsGeometry)
const deadCinematicDeclarations = findDeadCinematicDeclarations()

if (layoutViolations.length === 0 && surfaceViolations.length === 0 && deadCinematicDeclarations.length === 0) {
  console.log('CSS authority: layout owns geometry; surface owns visual semantics; cinematic carries no exact dead authority overrides.')
  process.exit(0)
}

if (layoutViolations.length > 0) {
  console.error('CSS authority violation: move visual semantics out of layout-authority.css.')
  for (const violation of layoutViolations) {
    console.error(`  src/layout-authority.css:${violation.line} ${violation.selector} -> ${violation.property}`)
  }
}

if (surfaceViolations.length > 0) {
  console.error('CSS authority violation: move geometry out of surface-authority.css.')
  for (const violation of surfaceViolations) {
    console.error(`  src/surface-authority.css:${violation.line} ${violation.selector} -> ${violation.property}`)
  }
}

if (deadCinematicDeclarations.length > 0) {
  console.error('CSS authority violation: cinematic contains declarations fully shadowed by final authority layers.')
  for (const violation of deadCinematicDeclarations) {
    console.error(`  ${path.relative(process.cwd(), violation.file)}:${violation.line} ${violation.selector} -> ${violation.property}`)
  }
}
process.exit(1)
