import { useId } from 'react'

/** Small material portraits share the studio's geometry without creating more GL contexts. */
export function SourceArtwork({ category, index, fit = 'slice' }: { category: string; index: number; fit?: 'slice' | 'meet' }) {
  const id = useId().replace(/:/g, '')
  const paint = (name: string) => `url(#${id}-${name})`
  const layered = category === 'academic'
  const fractured = category === 'vulnerability'
  return <svg className="source-artwork" viewBox="0 0 320 180" preserveAspectRatio={`xMidYMid ${fit}`} aria-hidden="true">
    <defs>
      <linearGradient id={`${id}-ground`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#f4f4eb"/><stop offset="1" stopColor="#d8ddcf"/></linearGradient>
      <linearGradient id={`${id}-metal`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#eef0e6"/><stop offset=".14" stopColor="#a1aaa1"/><stop offset=".37" stopColor="#334339"/><stop offset=".55" stopColor="#eef1e7"/><stop offset=".69" stopColor="#718277"/><stop offset="1" stopColor="#233329"/></linearGradient>
      <linearGradient id={`${id}-copper`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#f4d7b1"/><stop offset=".24" stopColor="#a76340"/><stop offset=".48" stopColor="#e4bd8f"/><stop offset=".8" stopColor="#7b452f"/><stop offset="1" stopColor="#d9a679"/></linearGradient>
      <linearGradient id={`${id}-glass`} x1="0" y1="0" x2=".8" y2="1"><stop stopColor="#fbfff6" stopOpacity=".85"/><stop offset=".3" stopColor="#abbca6" stopOpacity=".25"/><stop offset=".64" stopColor="#718977" stopOpacity=".65"/><stop offset="1" stopColor="#f1f5e9" stopOpacity=".5"/></linearGradient>
      <radialGradient id={`${id}-sphere`} cx=".3" cy=".2" r=".85"><stop stopColor="#8b9a8d"/><stop offset=".17" stopColor="#344a3c"/><stop offset=".65" stopColor="#14291d"/><stop offset="1" stopColor="#08130d"/></radialGradient>
      <filter id={`${id}-shadow`} x="-50%" y="-200%" width="200%" height="500%"><feGaussianBlur stdDeviation="5"/></filter>
    </defs>
    <rect width="320" height="180" fill={paint('ground')}/>
    <ellipse cx="165" cy="150" rx="67" ry="5" fill="#344336" opacity=".18" filter={paint('shadow')}/>
    <g transform={`translate(160 87) rotate(${index % 2 ? 4 : -4})`}>
      {layered ? <>
        <path d="M-5-49H5V51H-5Z" fill={paint('copper')}/>
        {[28, 11, -6, -23].map((y, i) => <g key={y} transform={`translate(0 ${y})`}>
          <path d="M0-33 70-2 0 33-70-2Z" fill={paint('glass')} stroke={paint(i === 3 ? 'copper' : 'metal')} strokeWidth="2.5"/>
          <path d="M-70-2 0 33 70-2v5L0 38-70 3Z" fill={paint('metal')}/>
          <path d="M-54-1 0 24 54-1" fill="none" stroke="#faffec" strokeOpacity=".65" strokeWidth=".7"/>
        </g>)}
        <circle cy="-59" r="5" fill={paint('copper')}/>
      </> : category === 'normative' ? <g transform="rotate(-8)">
        <path d="M-43-63H33L46-50V63H-43Z" fill={paint('metal')} stroke="#edf0e8" strokeWidth="1.3"/>
        <path d="M-29-49H31V50H-29Z" fill={paint('glass')} stroke={paint('copper')} strokeWidth="1.7"/>
        <path d="M-39-57v114" stroke={paint('copper')} strokeWidth="3"/>
        <path d="M-18-25H22m-40 15H22m-40 15H22m-40 15H11" stroke="#38513f" strokeOpacity=".7" strokeWidth="2.3"/>
        <path d="M-3-44v12m-8-6H5" stroke="#a46d4d" strokeWidth="1.5"/>
      </g> : category === 'vendor' ? <g transform="rotate(-13) scale(1 .86)">
        <circle r="65" fill={paint('metal')} stroke="#f5f5e8" strokeWidth="1.5"/>
        <circle r="55" fill={paint('sphere')} stroke={paint('copper')} strokeWidth="3"/>
        <circle r="39" fill="none" stroke="#e6ede2" strokeOpacity=".45" strokeWidth="1"/>
        <path d="M0-27 25-14v28L0 29l-25-15v-28Z" fill={paint('glass')} stroke={paint('metal')} strokeWidth="2"/>
        <path d="m-13 1 9 10 20-22" fill="none" stroke={paint('copper')} strokeWidth="4" strokeLinecap="round"/>
        <path d="M0-69v9m0 120v9M-69 0h9M60 0h9" stroke={paint('copper')} strokeWidth="2"/>
      </g> : category === 'incidents' ? <g transform="rotate(-17)">
        {[-30,0,30].map((x,i)=><g key={x} transform={`translate(${x} ${i*5-7})`}>
          <path d="M-18-53H12l9 9V51h-39Z" fill={paint(i===1?'copper':'metal')} stroke="#edf1e9" strokeWidth="1.2"/>
          <path d="M-8-34H10m-18 8H6m-14 8H9" stroke="#223529" strokeOpacity=".6" strokeWidth="1.7"/>
        </g>)}
        <ellipse cx="8" cy="-3" rx="73" ry="22" fill="none" stroke={paint('copper')} strokeWidth="1.6" transform="rotate(24)"/>
      </g> : category === 'development' ? <g transform="skewY(-14)">
        {[-42,0,42].map((x,i) => <g key={x} transform={`translate(${x} ${i*-4})`}>
          <path d="M-17-46H12L22-36V46H-7L-17 36Z M-6-32V31H10V-32Z" fill={paint(i===1?'copper':'metal')} fillRule="evenodd"/>
          <path d="M-17-46H12L22-36V46" fill="none" stroke="#f7f8ea" strokeWidth="1"/>
        </g>)}
      </g> : fractured ? <g transform="rotate(-13)">
        <path d="M-54-47-9-59v102l-45 14Z" fill={paint('sphere')} stroke={paint('metal')} strokeWidth="1.5"/>
        <path d="M1-47 45-57v103L1 58Z" fill={paint('metal')} stroke="#f7f7ec" strokeWidth=".6"/>
        <path d="M-3-49v101" stroke={paint('copper')} strokeWidth="3"/>
        <path d="M45-57 56-43v93L45 46Z" fill="#384c3c"/>
      </g> : category === 'assets' ? <>
        <path d="M0-65 61-9 0 58-61-9Z" fill={paint('glass')} stroke={paint('metal')} strokeWidth="1"/>
        <path d="M0-65v123L-61-9 0-28 61-9 0 58" fill="none" stroke="#f6f8ed" strokeWidth=".8"/>
        <path d="M-61-9 0-28 61-9 0 17Z" fill="#809980" opacity=".3"/>
        <ellipse rx="76" ry="17" cy="2" fill="none" stroke={paint('copper')} strokeWidth="2" transform="rotate(-17)"/>
      </> : category === 'independent' ? <g transform="rotate(-20) scale(1 .84)">
        <circle r="63" fill="#14231b" stroke={paint('metal')} strokeWidth="8"/>
        <circle r="54" fill="none" stroke={paint('copper')} strokeWidth="2"/>
        {Array.from({length:8},(_,i)=><path key={i} d="M0-49 34-36 31-7 9-19Z" transform={`rotate(${i*45})`} fill={paint('metal')} stroke="#cbd2c1" strokeOpacity=".35" strokeWidth=".5"/>)}
        <circle r="25" fill={paint('sphere')} stroke={paint('copper')} strokeWidth="1.5"/>
        <ellipse cx="-8" cy="-10" rx="12" ry="5" fill="#d6e6ca" opacity=".32"/>
      </g> : <>
        <ellipse rx="75" ry="29" fill="none" stroke={paint('copper')} strokeWidth="2" transform="rotate(35)"/>
        <circle r="48" fill={paint('sphere')}/>
        <path d="M-31-37A48 48 0 0 1 26-40" fill="none" stroke="#e1eddb" strokeOpacity=".75" strokeWidth="1"/>
        <ellipse rx="73" ry="22" fill="none" stroke={paint('metal')} strokeWidth="3" transform="rotate(-30)"/>
        <circle cx="61" cy="-33" r="4" fill={paint('copper')}/>
      </>}
    </g>
    <text x="18" y="25" fill="#65715e" fontSize="8" letterSpacing="2">{String(index+1).padStart(2,'0')} / {category.toUpperCase()}</text>
    <path d="M18 160h18m266 0h-18" stroke="#75816c" strokeOpacity=".4"/>
  </svg>
}
