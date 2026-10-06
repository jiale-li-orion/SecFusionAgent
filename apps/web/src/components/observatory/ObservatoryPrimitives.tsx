import type { Activity } from 'lucide-react'

export function PanelHead({ eyebrow, title, meta, icon: Icon }: { eyebrow: string; title: string; meta: string; icon: typeof Activity }) { return <div className="panel-head"><span className="panel-head-icon"><Icon size={15} /></span><div><small>{eyebrow}</small><strong>{title}</strong></div><span>{meta}</span></div> }
