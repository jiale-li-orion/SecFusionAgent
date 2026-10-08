import { useId } from 'react'

/** Material portraits, not activity simulations. The live accent follows measured role state. */
export function RoleSigil({ role, live }: { role: string; live: boolean }) {
  const id = useId().replace(/:/g, '')
  const oracle = role === 'DecisionRole'
  const argus = role === 'InvestigationRole'
  const accent = oracle ? '#c8d8ba' : argus ? '#bacbb0' : '#d5bea0'
  const paint = (name: string) => `url(#${id}-${name})`
  return <div className={`role-sigil ${oracle ? 'oracle' : argus ? 'argus' : 'alchemist'}-sigil ${live ? 'live' : ''}`} aria-hidden="true">
    <svg className="role-sculpture" viewBox="0 0 260 230">
      <defs>
        <radialGradient id={`${id}-halo`}><stop stopColor={accent} stopOpacity=".13"/><stop offset="1" stopColor={accent} stopOpacity="0"/></radialGradient>
        <radialGradient id={`${id}-sphere`} cx=".28" cy=".22" r=".8"><stop stopColor="#7a8879"/><stop offset=".12" stopColor="#41533f"/><stop offset=".42" stopColor="#233725"/><stop offset=".75" stopColor="#111f15"/><stop offset="1" stopColor="#070e08"/></radialGradient>
        <linearGradient id={`${id}-metal`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#e4e4df"/><stop offset=".15" stopColor="#8c9ba2"/><stop offset=".33" stopColor="#283540"/><stop offset=".52" stopColor="#11181f"/><stop offset=".7" stopColor="#536572"/><stop offset=".84" stopColor="#b5c4c9"/><stop offset="1" stopColor="#26313b"/></linearGradient>
        <linearGradient id={`${id}-foil`} x1="0" y1="0" x2="1" y2="1"><stop stopColor={accent}/><stop offset=".4" stopColor="#101821"/><stop offset=".7" stopColor={accent} stopOpacity=".45"/><stop offset="1" stopColor="#edf0e9"/></linearGradient>
        <linearGradient id={`${id}-glass`} x1="0" y1="0" x2=".8" y2="1"><stop stopColor="#c1d0b7" stopOpacity=".5"/><stop offset=".3" stopColor="#5e7a5a" stopOpacity=".2"/><stop offset="1" stopColor="#112319" stopOpacity=".9"/></linearGradient>
        <radialGradient id={`${id}-lens`} cx=".35" cy=".3"><stop stopColor="#dae5cc" stopOpacity=".45"/><stop offset=".3" stopColor="#3b5038"/><stop offset=".65" stopColor="#1c2f20"/><stop offset="1" stopColor="#07150c"/></radialGradient>
        <filter id={`${id}-blur`}><feGaussianBlur stdDeviation="7"/></filter>
      </defs>
      <ellipse cx="132" cy="202" rx="75" ry="8" fill="#000" opacity=".7" filter={paint('blur')}/>
      <ellipse cx="130" cy="109" rx="115" ry="106" fill={paint('halo')}/>
      {oracle ? <g>
        <circle cx="130" cy="106" r="73" fill={paint('sphere')} stroke={paint('metal')} strokeWidth="1.5"/>
        <path d="M78 55A73 73 0 0 1 190 65" fill="none" stroke="#e4ecdb" strokeWidth="1.5" opacity=".7"/>
        <ellipse cx="130" cy="106" rx="100" ry="28" transform="rotate(-31 130 106)" fill="none" stroke={paint('metal')} strokeWidth="2.5"/>
        <path d="M44 156Q86 158 162 109Q206 80 216 57" fill="none" stroke={paint('foil')} strokeWidth="3"/>
        <ellipse cx="112" cy="71" rx="23" ry="8" transform="rotate(-35 112 71)" fill="#e5edda" opacity=".07"/>
        <path d="M64 129Q70 177 119 181" fill="none" stroke={accent} strokeWidth=".5" opacity=".5"/>
        <circle cx="195" cy="65" r="2" fill={live ? '#d5efe6' : accent}/>
      </g> : argus ? <g transform="translate(130 108) rotate(-23) scale(1 .92)">
        <circle r="83" fill="#0d1e12" stroke={paint('metal')} strokeWidth="2"/>
        <circle r="76" fill="none" stroke={paint('metal')} strokeWidth="9"/>
        <circle r="68" fill="#14251a" stroke="#6c737d" strokeWidth=".6"/>
        {Array.from({ length: 8 }, (_, i) => <path key={i} d="M0-65 44-47 40-9 12-25Z" transform={`rotate(${i * 45})`} fill={paint('metal')} stroke="#acb5a0" strokeOpacity=".35" strokeWidth=".6"/>)}
        <circle r="35" fill={paint('lens')} stroke={paint('foil')} strokeWidth="2"/>
        <circle r="26" fill="none" stroke="#92a782" strokeOpacity=".25" strokeWidth=".6"/>
        <ellipse cx="-12" cy="-15" rx="14" ry="7" fill="#e5ebd9" opacity=".14" transform="rotate(-25)"/>
        <path d="M-77-23A80 80 0 0 1 39-70" fill="none" stroke="#f2f1dd" strokeOpacity=".75" strokeWidth="1.2"/>
        <circle cx="0" cy="-80" r="2" fill={live ? '#d5efe6' : accent}/>
      </g> : <g>
        {[34, 16, -2, -20].map((y, i) => <g key={y} transform={`translate(0 ${y})`}>
          <path d="M130 54 208 100 130 147 52 100Z" fill={paint(i === 3 ? 'glass' : 'metal')} stroke={paint('foil')} strokeWidth=".8"/>
          <path d="M52 100 130 147v15L52 115Z" fill="#1d2e21" stroke="#77848b" strokeWidth=".4"/>
          <path d="M130 147 208 100v15l-78 47Z" fill={paint('metal')} stroke="#8a9497" strokeWidth=".4"/>
          <path d="M63 100 130 139 197 100" fill="none" stroke={accent} strokeOpacity={i === 3 ? '.7' : '.2'} strokeWidth=".7"/>
        </g>)}
        <path d="M130 48 163 67 130 87 97 67Z" fill={paint('glass')} stroke="#ddd1bc" strokeWidth=".6"/>
        <path d="M130 54v85" stroke="#d6bd93" strokeWidth=".6" strokeOpacity=".4"/>
        <circle cx="130" cy="49" r="2" fill={live ? '#d5efe6' : accent}/>
      </g>}
      <path d="M28 208h26m152 0h26" stroke="#8797a1" strokeOpacity=".25" strokeWidth=".6"/>
    </svg>
  </div>
}
