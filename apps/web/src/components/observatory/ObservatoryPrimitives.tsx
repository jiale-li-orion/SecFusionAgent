import { productTerm } from '../../lib/productVocabulary'
import { useI18n } from '../../lib/i18n'
import { ProductGlyph } from '../instrument/ProductGlyph'
import type { Activity } from '../ui/icons'

export function PanelHead({ eyebrow, title, meta }: { eyebrow: string; title: string; meta: string; icon: typeof Activity }) { const { text } = useI18n(); return <div className="panel-head"><span className="panel-head-icon"><ProductGlyph kind={/SOURCE|WORLD/.test(eyebrow) ? 'world' : /AGENT|RUNTIME/.test(eyebrow) ? 'agents' : /SYSTEM|DEPEND/.test(eyebrow) ? 'assets' : 'observatory'} size={23} /></span><div><small>{productTerm(eyebrow, text)}</small><strong>{title}</strong></div><span>{meta}</span></div> }
