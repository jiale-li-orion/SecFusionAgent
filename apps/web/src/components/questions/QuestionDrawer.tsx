import { useRef, type ReactNode } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { X } from '../ui/icons'
import { useUiThemeClass } from '../ui/theme'
import { useI18n } from '../../lib/i18n'

export function QuestionDrawer({ open, onOpenChange, title, description, side, children }: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  side: 'left' | 'right'
  children: ReactNode
}) {
  const { text } = useI18n()
  const themeClass = useUiThemeClass()
  const previousFocus = useRef<HTMLElement | null>(null)
  return <Dialog.Root open={open} onOpenChange={onOpenChange}>
    <Dialog.Portal>
      <Dialog.Overlay className={`qa-drawer-overlay ${themeClass}`} />
      <Dialog.Content className={`qa-drawer qa-drawer-${side} ${themeClass}`} onOpenAutoFocus={() => { previousFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null }} onCloseAutoFocus={event => { event.preventDefault(); previousFocus.current?.focus() }}>
        <header className="qa-drawer-heading">
          <div><Dialog.Title>{title}</Dialog.Title><Dialog.Description>{description}</Dialog.Description></div>
          <Dialog.Close className="qa-icon-button" aria-label={text('关闭面板', 'Close panel')}><X size={20} /></Dialog.Close>
        </header>
        <div className="qa-drawer-content">{children}</div>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>
}
