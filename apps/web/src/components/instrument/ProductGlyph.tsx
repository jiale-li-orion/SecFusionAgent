import { useId } from 'react'

/** Product symbols share a cut-metal geometry; navigation never relies on the symbol alone. */
export function ProductGlyph({ kind, size = 24, className = '' }: { kind: string; size?: number; className?: string }) {
  const id = useId().replace(/:/g, '')
  const paths: Record<string, string[]> = {
    world: ['M16 3 28 10v13L16 30 4 23V10Z', 'M4 10l12 7 12-7M16 17v13M10 7l12 7v12'],
    intelligence: ['M5 9 16 3 27 9 16 15Z', 'M5 15l11 6 11-6M5 21l11 6 11-6'],
    investigations: ['M16 3 28 16 16 29 4 16Z', 'M10 10h12v12H10Z', 'M16 3v7m12 6h-6m-6 13v-7M4 16h6'],
    agents: ['M16 3 26 9v12l-10 6-10-6V9Z', 'M11 12h10v8H11Z', 'M16 3v5m-5 19v3m10-3v3M2 12h4m20 6h4'],
    observatory: ['M4 26h24M6 22V11m7 11V6m7 16V15m7 7V3', 'M4 14l9-7 7 9 8-12'],
    start: ['M9 4h14l6 12-6 12H9L3 16Z', 'M13 10l9 6-9 6Z'],
    vulnerability: ['M16 3 28 10v13l-12 7L4 23V10Z', 'M18 4l-7 11 8 2-5 12'],
    development: ['M5 7h12v18H5ZM15 4h12v18H15Z', 'M9 12h4m-4 5h4m6-8h4m-4 5h4'],
    academic: ['M5 6 16 10 27 6v19l-11 4-11-4Z', 'M16 10v19M8 3l8 3 8-3'],
    vendor: ['M16 3 27 7v12l-11 11L5 19V7Z', 'M16 9l6 6-6 6-6-6Z'],
    normative: ['M7 4h19v22H7Z', 'M7 9H4v20h19v-3M12 11h9m-9 5h9m-9 5h5'],
    independent: ['M16 3 22 16 16 29 10 16Z', 'M5 7v18M27 7v18M10 16h12'],
    assets: ['M16 3 28 16 16 29 4 16Z', 'M16 3v26M4 16h24M4 16l12-6 12 6-12 6Z'],
    incidents: ['M5 8h13l9 9v10H14l-9-9Z', 'M5 14h13l9 9M11 3h12l6 6v9'],
    verify: ['M16 3 27 7v12l-11 11L5 19V7Z', 'M10 16l4 4 9-9'],
    lookup: ['M6 4h17v20H6Z', 'M11 10h7m-7 5h5M20 20l8 8'],
    trace: ['M16 3 28 16 16 29 4 16Z', 'M10 16h12M16 10v12'],
    deep: ['M4 8 16 2 28 8 16 14Z', 'M4 14l12 6 12-6M4 20l12 6 12-6M16 14v12'],
    monitor: ['M4 8h24v17H4Z', 'M8 17h4l3-6 4 10 3-4h3M12 29h8m-4-4v4'],
    watch: ['M4 8h24v17H4Z', 'M8 17h4l3-6 4 10 3-4h3M12 29h8m-4-4v4'],
    wide: ['M4 5h9v9H4Zm15 0h9v9h-9ZM4 20h9v9H4Zm15 0h9v9h-9Z'],
    full: ['M4 5h9v9H4Zm15 0h9v9h-9ZM4 20h9v9H4Zm15 0h9v9h-9Z'],
  }
  return <svg className={`product-glyph ${className}`} width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true"><defs><linearGradient id={id} x1="3" y1="2" x2="27" y2="30" gradientUnits="userSpaceOnUse"><stop stopColor="currentColor"/><stop offset=".45" stopColor="currentColor" stopOpacity=".9"/><stop offset="1" stopColor="currentColor" stopOpacity=".4"/></linearGradient></defs>{(paths[({ direct: 'start', retrieve: 'intelligence', investigate: 'investigations' } as Record<string, string>)[kind.toLowerCase()] ?? kind.toLowerCase()] ?? paths.intelligence).map((d, i) => <path key={d} d={d} stroke={`url(#${id})`} strokeWidth={i === 0 ? 1.3 : 1} strokeLinejoin="round" strokeLinecap="round" fill={i === 0 ? 'currentColor' : 'none'} fillOpacity={i === 0 ? .035 : 0}/>)}</svg>
}

export function BrandMark({ size = 34 }: { size?: number }) {
  return <svg className="brand-mark" width={size} height={size} viewBox="0 0 40 40" fill="none" aria-hidden="true"><path d="M20 2 36 11v18L20 38 4 29V11Z" stroke="currentColor" strokeOpacity=".38"/><path d="M29 12H18l-7 7 7 7h11M11 28h11l7-7-7-7H11" stroke="currentColor" strokeWidth="2"/><path d="m20 2 16 9M4 29l16 9" stroke="currentColor" strokeWidth="1.8"/></svg>
}
