import { useId } from 'react'

const aliases: Record<string, string> = {
  direct: 'start', retrieve: 'intelligence', investigate: 'investigations',
  watch: 'observatory', monitor: 'observatory', lookup: 'intelligence',
  verify: 'vulnerability', trace: 'investigations', deep: 'intelligence',
  wide: 'world', full: 'world',
}

/** Eight source seals and six space marks share a machined rim, not an icon font. */
export function ProductGlyph({ kind, size = 24, className = '' }: { kind: string; size?: number; className?: string }) {
  const id = useId().replace(/:/g, '')
  const motif = aliases[kind.toLowerCase()] ?? kind.toLowerCase()
  return <svg className={`product-glyph product-glyph-${motif} ${className}`} width={size} height={size} viewBox="0 0 40 40" fill="none" aria-hidden="true">
    <defs><linearGradient id={`${id}-rim`} x1="4" y1="4" x2="36" y2="36" gradientUnits="userSpaceOnUse"><stop stopColor="currentColor" stopOpacity=".8"/><stop offset=".52" stopColor="currentColor" stopOpacity=".22"/><stop offset="1" stopColor="currentColor" stopOpacity=".66"/></linearGradient></defs>
    <path d="M20 2.5 35.15 11.25v17.5L20 37.5 4.85 28.75v-17.5Z" fill="currentColor" fillOpacity=".045" stroke={`url(#${id}-rim)`} strokeWidth=".9"/>
    <path d="M20 5.5 32.55 12.75v14.5L20 34.5 7.45 27.25v-14.5Z" stroke="currentColor" strokeOpacity=".13" strokeWidth=".7"/>
    {motif === 'world' && <g stroke="currentColor" strokeLinecap="round" strokeLinejoin="round"><path d="M10 22.6 20 16l10 6.6-10 6.7Z" fill="currentColor" fillOpacity=".16" strokeWidth="1.2"/><path d="m10 17.2 10-6.5 10 6.5M20 10.7V16m0 13.3v4.1M10 22.6l-3 2m23-2 3 2" strokeWidth="1.5"/><circle cx="20" cy="16" r="1.6" fill="currentColor" stroke="none"/></g>}
    {motif === 'intelligence' && <g stroke="currentColor" strokeLinejoin="round"><path d="m9 25 11-5 11 5-11 5Z" fill="currentColor" fillOpacity=".17" strokeWidth="1.2"/><path d="m9 20 11-5 11 5-11 5Zm0-5 11-5 11 5-11 5Z" strokeWidth="1.4"/><path d="M20 10v10" strokeOpacity=".5"/></g>}
    {motif === 'investigations' && <g stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"><path d="M20 8 31 20 20 32 9 20Z" fill="currentColor" fillOpacity=".1"/><path d="M13 20h14M20 13v14"/><circle cx="20" cy="20" r="4.2" fill="currentColor" fillOpacity=".23"/><path d="m27.8 12.2 3-3m-21 21 3-3"/></g>}
    {motif === 'agents' && <g stroke="currentColor" strokeLinejoin="round"><path d="M20 8 30 14v12l-10 6-10-6V14Z" fill="currentColor" fillOpacity=".12" strokeWidth="1.2"/><circle cx="20" cy="20" r="5.3" strokeWidth="1.4"/><path d="M20 8v6m10 0-5.2 3M10 26l5.2-3m4.8 3v6" strokeWidth="1.4"/><circle cx="20" cy="20" r="1.5" fill="currentColor" stroke="none"/></g>}
    {motif === 'observatory' && <g stroke="currentColor" strokeLinecap="round"><path d="M9 27V13m6 14V19m5 8V9m6 18V16m5 11v-9" strokeWidth="2.2"/><path d="M8 29h24M9 12l6 6 5-8 6 5 5-4" strokeOpacity=".56" strokeWidth="1.1"/></g>}
    {motif === 'start' && <g stroke="currentColor" strokeLinejoin="round"><path d="M11 9h18l5 11-5 11H11L6 20Z" fill="currentColor" fillOpacity=".13" strokeWidth="1.25"/><path d="m16 13 11 7-11 7Z" fill="currentColor" fillOpacity=".35" strokeWidth="1.25"/><path d="M10 20h5" strokeWidth="1.4"/></g>}
    {motif === 'vulnerability' && <g stroke="currentColor" strokeLinejoin="round"><path d="M20 8 30 14v12l-10 6-10-6V14Z" fill="currentColor" fillOpacity=".16" strokeWidth="1.2"/><path d="m22 8-8 12 9 1-5 11" strokeWidth="2.2"/><path d="m10 14 6 3m8 9 6-2" strokeOpacity=".5"/></g>}
    {motif === 'development' && <g stroke="currentColor" strokeLinecap="round" strokeLinejoin="round"><path d="M11 11v17m0-11h15m0 0v11" strokeWidth="1.6"/><circle cx="11" cy="11" r="3" fill="currentColor" fillOpacity=".3" strokeWidth="1.4"/><circle cx="11" cy="28" r="3" fill="currentColor" fillOpacity=".3" strokeWidth="1.4"/><circle cx="26" cy="17" r="3" fill="currentColor" fillOpacity=".3" strokeWidth="1.4"/><circle cx="26" cy="28" r="3" fill="currentColor" fillOpacity=".3" strokeWidth="1.4"/></g>}
    {motif === 'academic' && <g stroke="currentColor" strokeLinejoin="round"><path d="m9 14 11-5 11 5-11 5Z" fill="currentColor" fillOpacity=".22" strokeWidth="1.4"/><path d="M11 18v10l9 4 9-4V18M20 19v13" strokeWidth="1.5"/><path d="m14 23 6 3 6-3" strokeOpacity=".5"/></g>}
    {motif === 'vendor' && <g stroke="currentColor" strokeLinejoin="round"><path d="M20 8 30 12v12l-10 8-10-8V12Z" fill="currentColor" fillOpacity=".14" strokeWidth="1.3"/><path d="m14 20 4 4 8-9" strokeWidth="2.25" strokeLinecap="round"/><path d="M15 10v3m10-3v3" strokeOpacity=".6"/></g>}
    {motif === 'normative' && <g stroke="currentColor" strokeLinejoin="round"><path d="M12 9h16v21H12Z" fill="currentColor" fillOpacity=".12" strokeWidth="1.3"/><path d="M16 9v21m4-15h5m-5 5h5m-5 5h3" strokeWidth="1.4"/><path d="M9 13h3m-3 13h3" strokeWidth="1.7"/></g>}
    {motif === 'independent' && <g stroke="currentColor" strokeLinecap="round"><circle cx="20" cy="20" r="3" fill="currentColor" strokeWidth="1.2"/><path d="M12 12a11.3 11.3 0 0 0 0 16m16-16a11.3 11.3 0 0 1 0 16M8 8a17 17 0 0 0 0 24m24-24a17 17 0 0 1 0 24" strokeWidth="1.5"/></g>}
    {motif === 'assets' && <g stroke="currentColor" strokeLinejoin="round"><path d="m20 9 11 6v12l-11 6-11-6V15Z" fill="currentColor" fillOpacity=".1" strokeWidth="1.2"/><path d="m9 15 11 7 11-7M20 22v11m-6-15 11-6" strokeWidth="1.4"/><circle cx="20" cy="22" r="2" fill="currentColor" stroke="none"/></g>}
    {motif === 'incidents' && <g stroke="currentColor" strokeLinejoin="round"><path d="M10 12h11l9 9v10H19l-9-9Z" fill="currentColor" fillOpacity=".13" strokeWidth="1.2"/><path d="M10 18h11l9 9M15 8h11l5 5v7" strokeWidth="1.3"/><circle cx="21" cy="21" r="2" fill="currentColor" stroke="none"/></g>}
  </svg>
}

/** Evidence aperture: independently entering planes meet at one durable centre. */
export function BrandMark({ size = 38 }: { size?: number }) {
  const id = useId().replace(/:/g, '')
  return <svg className="brand-mark" width={size} height={size} viewBox="0 0 48 48" fill="none" aria-hidden="true">
    <defs><linearGradient id={`${id}-brand`} x1="7" y1="3" x2="41" y2="45" gradientUnits="userSpaceOnUse"><stop stopColor="#35463b"/><stop offset=".5" stopColor="#18291f"/><stop offset="1" stopColor="#0e1d15"/></linearGradient><linearGradient id={`${id}-edge`} x1="7" y1="5" x2="40" y2="44" gradientUnits="userSpaceOnUse"><stop stopColor="#c8d5ba"/><stop offset=".52" stopColor="#667d6a"/><stop offset="1" stopColor="#c2a17b"/></linearGradient></defs>
    <path d="M24 2.5 42.6 13.25v21.5L24 45.5 5.4 34.75v-21.5Z" fill={`url(#${id}-brand)`} stroke={`url(#${id}-edge)`} strokeWidth="1.2"/>
    <path d="m24 7 14.6 8.4v17.2L24 41 9.4 32.6V15.4Z" stroke="#dce7d7" strokeOpacity=".28" strokeWidth=".7"/>
    <path d="m11 17 13-7.5L37 17 24 24.5Z" fill="#dce6d3" fillOpacity=".83"/>
    <path d="M11 17v14l13 7.5v-14Z" fill="#809989"/>
    <path d="M37 17v14l-13 7.5v-14Z" fill="#415c4b"/>
    <path d="m17.2 20.6 6.8-3.9 6.8 3.9L24 24.5Z" fill="#15261c"/>
    <path d="M17.2 20.6v7.9l6.8 3.9v-7.9Z" fill="#203529"/>
    <path d="M30.8 20.6v7.9L24 32.4v-7.9Z" fill="#091d12"/>
    <path d="M11 31 24 38.5 37 31M24 9.5v7.2" stroke="#dbe8d4" strokeOpacity=".67" strokeWidth=".8"/>
    <circle cx="24" cy="24.5" r="2.1" fill="#d0ab7e"/>
  </svg>
}
