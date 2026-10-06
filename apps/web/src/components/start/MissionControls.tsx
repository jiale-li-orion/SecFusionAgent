export function ModeInstrument({ mode, active }: { mode: string; active: boolean }) {
  if (mode === 'DIRECT') {
    return <span className={'mode-instrument direct ' + (active ? 'active' : '')} aria-hidden="true"><i /><i /><b /></span>
  }
  if (mode === 'RETRIEVE') {
    return <span className={'mode-instrument retrieve ' + (active ? 'active' : '')} aria-hidden="true"><i /><i /><i /><b /></span>
  }
  if (mode === 'VERIFY') {
    return <span className={'mode-instrument verify ' + (active ? 'active' : '')} aria-hidden="true"><i /><i /><b /></span>
  }
  if (mode === 'INVESTIGATE') {
    return <span className={'mode-instrument investigate ' + (active ? 'active' : '')} aria-hidden="true"><i /><i /><i /><i /><b /></span>
  }
  return <span className={'mode-instrument watch ' + (active ? 'active' : '')} aria-hidden="true"><i /><i /><b /></span>
}

export function AdvancedRange({ label, value, min, max, step, onChange, suffix }: { label: string; value: number; min: number; max: number; step: number; onChange: (value: number) => void; suffix: string }) {
  return (
    <label className="advanced-range">
      <span><small>{label}</small><strong>{value}{suffix}</strong></span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  )
}

export function ModeFact({ label, value }: { label: string; value: string }) {
  return <span><small>{label}</small><strong>{value}</strong></span>
}
