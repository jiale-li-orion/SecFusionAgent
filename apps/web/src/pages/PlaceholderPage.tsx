import { ArrowUpRight, Orbit } from 'lucide-react'

export function PlaceholderPage({ eyebrow, title, description, items }: { eyebrow: string; title: string; description: string; items: string[] }) {
  return (
    <section className="page placeholder-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          <p className="lede">{description}</p>
        </div>
      </div>
      <div className="placeholder-stage panel-glass">
        <Orbit size={56} strokeWidth={1.2} />
        <div>
          <small>PRODUCT P0 / CONNECTING READ MODEL</small>
          <strong>这不是空白页：视觉 shell 已经统一，下一刀直接接真实 owner。</strong>
        </div>
      </div>
      <div className="placeholder-grid">
        {items.map((item) => <article key={item} className="panel-glass placeholder-card"><span>{item}</span><ArrowUpRight size={16} /></article>)}
      </div>
    </section>
  )
}
