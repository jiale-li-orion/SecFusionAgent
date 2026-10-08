import { HeroArtifact } from '../instrument/HeroArtifact'
import { ProductGlyph } from '../instrument/ProductGlyph'
import { SourceArtwork } from '../instrument/SourceArtwork'
import { useState } from 'react'
import { ArrowUpRight, ArrowRight } from 'lucide-react'
import { motion, useReducedMotion } from 'motion/react'
import type { WorldStory } from '../../lib/api/world'
import { useI18n } from '../../lib/i18n'

const kinds = [
  {key:'academic',zh:'研究',en:'Research'}, {key:'development',zh:'开发',en:'Development'},
  {key:'vulnerability',zh:'漏洞',en:'Vulnerabilities'}, {key:'vendor',zh:'厂商',en:'Vendors'},
  {key:'normative',zh:'标准',en:'Standards'}, {key:'independent',zh:'独立情报',en:'Independent'},
  {key:'assets',zh:'资产',en:'Assets'}, {key:'incidents',zh:'事件',en:'Incidents'},
]
export function IntelligenceIndex({ stories, loading, error, onSelect }: { stories: WorldStory[]; loading: boolean; error: string | null; onSelect: (s: WorldStory) => void }) {
  const {text}=useI18n(); const reduced=useReducedMotion()
  const [category,setCategory]=useState<string|null>(null)
  const [previewId,setPreviewId]=useState<string|null>(null)
  const items=stories.filter(s=>(s.object_id||s.incident_id)&&(!category||s.category===category))
  const selected=items.find(s=>s.story_id===previewId)??items[0]
  const kind=kinds.find(k=>k.key===selected?.category)
  return <section className="vision-library">
    <div className="catalog-filters"><button className={!category?'active':''} aria-pressed={!category} onClick={()=>setCategory(null)}>{text('全部资料','All material')}</button>{kinds.map(k=><button key={k.key} className={category===k.key?'active':''} aria-pressed={category===k.key} onClick={()=>setCategory(k.key)}><ProductGlyph kind={k.key} size={17}/>{text(k.zh,k.en)}</button>)}</div>
    {selected && <motion.article key={selected.story_id} className="vision-folio" initial={reduced?false:{opacity:0,y:10}} animate={{opacity:1,y:0}} transition={{duration:.25}}><div className="vision-folio-copy"><div className="vision-material-origin"><ProductGlyph kind={selected.category} size={22}/><span>{kind?text(kind.zh,kind.en):selected.category}</span><i/><span>{selected.source_name?.split(' · ')[0]??selected.category}</span></div><h2>{selected.headline}</h2>{selected.excerpt&&<blockquote>{selected.excerpt}</blockquote>}<div className="vision-folio-actions"><button className="ew-primary" onClick={()=>onSelect(selected)}>{text('打开完整档案','Open dossier')}<ArrowRight size={17}/></button>{selected.external_ref&&<a href={selected.external_ref} target="_blank" rel="noreferrer">{text('来源原文','Original source')}<ArrowUpRight size={14}/></a>}</div><time>{text('收录于','Retained')} {new Date(selected.observed_at).toLocaleDateString()}</time></div><div className="vision-folio-art"><HeroArtifact kind={selected.category}/><span>{kind?text(kind.zh,kind.en):selected.category}</span></div></motion.article>}
    <div className="vision-shelf-heading"><span>{text('在材料之间探索','EXPLORE THE COLLECTION')}</span><small>{loading?text('读取中…','Loading…'):text(`${items.length} 份已载入资料`,`${items.length} loaded objects`)}</small></div>
    <div className="vision-folio-shelf">{items.map((s,i)=><button key={s.story_id} aria-pressed={selected?.story_id===s.story_id} onClick={()=>setPreviewId(s.story_id)} className={`vision-shelf-item ${selected?.story_id===s.story_id?'selected':''}`}><div><SourceArtwork category={s.category} index={i}/><ProductGlyph kind={s.category} size={18}/></div><small>{s.source_name?.split(' · ')[0]??s.category}</small><strong>{s.headline}</strong></button>)}</div>
    {error&&<p role="alert">{error}</p>}{!loading&&!items.length&&<p className="catalog-empty">{text('这一类别暂时没有载入的资料。选择其他类别，或搜索对象。','No loaded material in this category. Choose another category or search for an object.')}</p>}
  </section>
}
