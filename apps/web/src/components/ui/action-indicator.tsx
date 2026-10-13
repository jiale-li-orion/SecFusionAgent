import { cn } from '../../lib/cn'
import { ArrowRight, ArrowUpRight, ChevronDown } from './icons'

/** Decorative direction cue; the containing row owns the accessible name and click target. */
export function ActionIndicator({ direction = 'forward', className }: {
  direction?: 'forward' | 'external' | 'expand'
  className?: string
}) {
  const Icon = direction === 'external' ? ArrowUpRight : direction === 'expand' ? ChevronDown : ArrowRight
  return <span data-slot="action-indicator" data-direction={direction} className={cn('ui-action-indicator', className)} aria-hidden="true">
    <Icon size={15} weight="bold" />
  </span>
}
