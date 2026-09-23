#!/usr/bin/env node
/**
 * Builds the GitHub Pages site for SecFusionAgent.
 *
 * Source of truth is the project wiki (a separate git repository), so this
 * repository stays free of documentation copies. The workflow clones the public
 * wiki, this script renders its Markdown to static HTML, and pulls the diagram
 * assets that already live in the wiki into the same site.
 *
 * Usage: node .github/pages/build.mjs <wikiDir> <outDir>
 */
import { readdir, readFile, writeFile, mkdir, cp } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { marked } from 'marked'

const wikiDir = process.argv[2] || 'wiki'
const outDir = process.argv[3] || '_site'
const repo = process.env.GITHUB_REPOSITORY || 'jiale-li-orion/SecFusionAgent'
const [owner, name] = repo.split('/')
const diagramHtml = 'prd-flow/prd-requirements-flow.html'
const BRAND = 'SecFusionAgent'

const esc = (s) =>
  String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

const titleOf = (md, fallback) => {
  const m = md.match(/^#\s+(.+)$/m)
  return m ? m[1].trim() : fallback
}

const slugOf = (file) => (file === 'Home.md' ? 'index' : file.replace(/\.md$/, ''))

/** Short nav label: 首页 for Home, otherwise the heading without a leading brand name. */
const navLabel = (page) =>
  page.slug === 'index' ? '首页' : page.title.replace(new RegExp(`^${BRAND}\\s+`), '')

const css = `
:root { color-scheme: light dark; --bg:#ffffff; --fg:#1f2430; --muted:#5b6675; --line:#e3e8ef;
        --panel:#f7f9fc; --accent:#0b6bcb; --code:#f2f5f9; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#0d1117; --fg:#e6edf3; --muted:#9aa7b4; --line:#232b36; --panel:#151b23;
          --accent:#6cb6ff; --code:#1b222c; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
       font:16px/1.7 -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", "PingFang SC",
            "Microsoft YaHei", Roboto, Helvetica, Arial, sans-serif; }
a { color:var(--accent); }
.topbar { position:sticky; top:0; z-index:2; display:flex; flex-wrap:wrap; gap:.5rem 1rem;
          align-items:center; padding:.75rem 1.25rem; background:color-mix(in srgb, var(--bg) 88%, transparent);
          backdrop-filter:blur(8px); border-bottom:1px solid var(--line); }
.brand { font-weight:700; text-decoration:none; color:var(--fg); }
.topbar nav { display:flex; flex-wrap:wrap; gap:.25rem .9rem; font-size:.9rem; }
.topbar nav a { text-decoration:none; color:var(--muted); padding:.15rem 0; }
.topbar nav a:hover { color:var(--accent); }
.topbar nav a[aria-current="page"] { color:var(--fg); font-weight:600; }
main { max-width:920px; margin:0 auto; padding:1.75rem 1.25rem 4rem; }
h1 { font-size:1.7rem; line-height:1.3; margin:.2rem 0 1rem; }
h2 { font-size:1.25rem; margin:2.2rem 0 .7rem; padding-bottom:.35rem; border-bottom:1px solid var(--line); }
h3 { font-size:1.05rem; margin:1.6rem 0 .5rem; }
img { max-width:100%; height:auto; border:1px solid var(--line); border-radius:8px; background:var(--bg); }
code { background:var(--code); padding:.12em .38em; border-radius:4px; font-size:.9em;
       font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
pre { background:var(--code); padding:.9rem 1rem; border-radius:8px; overflow-x:auto; border:1px solid var(--line); }
pre code { background:none; padding:0; }
table { border-collapse:collapse; width:100%; margin:1rem 0; font-size:.94rem; display:block; overflow-x:auto; }
th, td { border:1px solid var(--line); padding:.5rem .7rem; text-align:left; vertical-align:top; }
th { background:var(--panel); }
blockquote { margin:1rem 0; padding:.4rem 1rem; border-left:3px solid var(--line); color:var(--muted); }
ul, ol { padding-left:1.3rem; }
hr { border:0; border-top:1px solid var(--line); margin:2rem 0; }
.callout { margin:1.2rem 0; padding:.8rem 1rem; border:1px solid var(--line); border-left:4px solid var(--accent);
           border-radius:8px; background:var(--panel); font-size:.95rem; }
footer { max-width:920px; margin:0 auto; padding:1.5rem 1.25rem 3rem; color:var(--muted);
         font-size:.85rem; border-top:1px solid var(--line); }
`

function layout({ title, nav, body }) {
  const docTitle = title.trim().toLowerCase() === BRAND.toLowerCase() ? title : `${title} · ${BRAND}`
  return `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(docTitle)}</title>
<style>${css}</style>
</head>
<body>
<header class="topbar">
  <a class="brand" href="index.html">SecFusionAgent</a>
  <nav>${nav}</nav>
</header>
<main>
${body}
</main>
<footer>
  SecFusionAgent · 站点内容自动构建自
  <a href="https://github.com/${owner}/${name}/wiki">项目 wiki</a>（
  <code>${owner}/${name}</code>）。需求变更以 wiki 为准。
</footer>
</body>
</html>
`
}

/** Wiki-relative Markdown links become site-relative .html links. */
function rewriteLinks(html) {
  // local asset copies first: raw wiki URLs -> same-origin paths
  let out = html.replaceAll(
    `https://raw.githubusercontent.com/wiki/${owner}/${name}/`,
    ''
  )
  // page links written as [text](Page-Name) in the wiki
  out = out.replace(/href="([^"#:/][^":]*?)"/g, (all, target) => {
    if (/\.(html?|md|png|jpe?g|svg|webm|json)$/i.test(target)) return all
    return `href="${target}.html"`
  })
  return out
}

async function main() {
  const files = (await readdir(wikiDir)).filter((f) => f.endsWith('.md')).sort()
  if (!files.length) throw new Error(`no markdown pages found in ${wikiDir}`)
  // Home first, then the rest in alphabetical order.
  const ordered = files.includes('Home.md')
    ? ['Home.md', ...files.filter((f) => f !== 'Home.md')]
    : files

  await mkdir(outDir, { recursive: true })

  const pages = []
  for (const file of ordered) {
    const md = await readFile(join(wikiDir, file), 'utf8')
    pages.push({ file, slug: slugOf(file), title: titleOf(md, file.replace(/\.md$/, '')), md })
  }

  const hasDiagram = existsSync(join(wikiDir, diagramHtml))

  for (const page of pages) {
    const nav = pages
      .map((p) => {
        const current = p.slug === page.slug ? ' aria-current="page"' : ''
        return `<a href="${p.slug}.html"${current}>${esc(navLabel(p))}</a>`
      })
      .join('\n    ')
    const diagramNav = hasDiagram
      ? `\n    <a href="${diagramHtml}">交互图 ↗</a>`
      : ''

    const rendered = rewriteLinks(marked.parse(page.md))
    // On the Pages site the interactive diagram is served directly, so point at it.
    const callout =
      hasDiagram && page.slug === 'Requirements-Flow-Diagram'
        ? `<div class="callout">本站可直接打开<b>交互版图</b>（主题切换、缩放、搜索、导出，另存为单文件即可离线使用）：<a href="${diagramHtml}">prd-requirements-flow.html ↗</a></div>\n`
        : ''

    await writeFile(
      join(outDir, `${page.slug}.html`),
      layout({ title: page.title, nav: nav + diagramNav, body: callout + rendered }),
      'utf8'
    )
  }

  if (hasDiagram) {
    await cp(join(wikiDir, 'prd-flow'), join(outDir, 'prd-flow'), { recursive: true })
  }

  console.log(`built ${pages.length} page(s) -> ${outDir}${hasDiagram ? ' (+ prd-flow assets)' : ''}`)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
