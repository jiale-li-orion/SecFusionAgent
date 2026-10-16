import { cn } from '../../lib/cn'
import { ChevronDown } from './icons'

/** Disclosure affordance only. Plain navigation no longer appends a boxed arrow. */
export function ActionIndicator({ className }: { className?: string }) {
  return <span data-slot="action-indicator" className={cn('ui-action-indicator', className)} aria-hidden="true"><ChevronDown size={15} /></span>
}
