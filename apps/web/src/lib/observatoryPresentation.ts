export const observatoryWindows = ['1h', '6h', '24h', '168h'] as const
export type ObservatoryWindow = (typeof observatoryWindows)[number]

export function linePath(values: Array<number | null>, width: number, height: number, max: number) {
  let connected = false
  return values.flatMap((value, index) => {
    if (value == null || !Number.isFinite(value)) { connected = false; return [] }
    const x = values.length === 1 ? width / 2 : index / (values.length - 1) * width
    const y = height - Math.min(value / max, 1) * (height - 10) - 5
    const point = `${connected ? 'L' : 'M'} ${x} ${y}`
    connected = true
    return [point]
  }).join(' ')
}

export function numeric(value: number | string | null | undefined) { return typeof value === 'number' ? value : typeof value === 'string' ? Number(value) || 0 : 0 }

export function seconds(value: number | null | undefined) { return value == null ? '—' : value < 1 ? `${(value * 1000).toFixed(0)}ms` : `${value.toFixed(value < 10 ? 2 : 1)}s` }

export function pct(value: number) { return `${(value * 100).toFixed(value >= .995 ? 0 : 1)}%` }

export function compactNumber(value: number) { return Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(value) }

export function bytes(value: number) { return value < 1024 ? `${value} B` : value < 1024 ** 2 ? `${(value / 1024).toFixed(1)} KiB` : `${(value / 1024 ** 2).toFixed(1)} MiB` }

export function formatNumber(value: number) { return Math.abs(value) < 10 ? value.toFixed(3).replace(/0+$/, '').replace(/\.$/, '') : value.toFixed(0) }

export function snapshotAge(value: string) { const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000)); if (seconds < 60) return `${seconds}s ago`; const minutes = Math.floor(seconds / 60); if (minutes < 60) return `${minutes}m ago`; const hours = Math.floor(minutes / 60); return hours < 48 ? `${hours}h ago` : `${Math.floor(hours / 24)}d ago` }
