import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

/** A shared visual treatment for functional symbols, never an independent control. */
export function IconTile({ children, tone = 'cobalt', compact = false, className }: {
  children: ReactNode
  tone?: 'cobalt' | 'violet' | 'teal' | 'slate'
  compact?: boolean
  className?: string
}) {
  return <span aria-hidden="true" className={cn('ui-icon-tile', className)} data-tone={tone} data-compact={compact}>
    <span className="ui-icon-tile-glyph">{children}</span>
  </span>
}
