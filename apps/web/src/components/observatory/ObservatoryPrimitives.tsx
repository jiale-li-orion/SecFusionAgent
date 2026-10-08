import { ProductGlyph } from '../instrument/ProductGlyph'
import type { Activity } from 'lucide-react'

export function PanelHead({ eyebrow, title, meta }: { eyebrow: string; title: string; meta: string; icon: typeof Activity }) { return <div className="panel-head"><span className="panel-head-icon"><ProductGlyph kind={/SOURCE|WORLD/.test(eyebrow) ? 'world' : /AGENT|RUNTIME/.test(eyebrow) ? 'agents' : /SYSTEM|DEPEND/.test(eyebrow) ? 'assets' : 'observatory'} size={23} /></span><div><small>{eyebrow}</small><strong>{title}</strong></div><span>{meta}</span></div> }
