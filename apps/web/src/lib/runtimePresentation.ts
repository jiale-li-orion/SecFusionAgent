export type RuntimeCount = readonly [name: string, count: number]

export function rankRuntimeCounts(values: Record<string, number>, limit = Number.POSITIVE_INFINITY): RuntimeCount[] {
  return Object.entries(values)
    .sort((left, right) => right[1] - left[1])
    .slice(0, limit)
}

export function dominantRuntimeName(values: Record<string, number>) {
  return rankRuntimeCounts(values, 1)[0]?.[0] ?? null
}

export function runtimeToken(value: string) {
  return value.replaceAll('_', ' ').replaceAll('-', ' ').toUpperCase()
}
