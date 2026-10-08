import { useEffect, useRef, useState } from 'react'

/** Reveal only text already received from SSE, one or two Unicode code points per frame. */
export function usePacedStreamText(target: string): string {
  const [visible, setVisible] = useState('')
  const visibleRef = useRef('')
  const targetRef = useRef(target)
  const frameRef = useRef<number | null>(null)

  useEffect(() => {
    targetRef.current = target
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current)
      frameRef.current = null
      visibleRef.current = target
      return
    }

    if (frameRef.current !== null || target === visibleRef.current) return

    const advance = () => {
      frameRef.current = null
      const received = targetRef.current
      const current = visibleRef.current
      if (!received.startsWith(current)) {
        visibleRef.current = ''
        setVisible('')
      } else if (received.length > current.length) {
        const remaining = Array.from(received.slice(current.length))
        const count = remaining.length > 80 ? 2 : 1
        const next = current + remaining.slice(0, count).join('')
        visibleRef.current = next
        setVisible(next)
      }
      if (visibleRef.current !== targetRef.current) frameRef.current = requestAnimationFrame(advance)
    }
    frameRef.current = requestAnimationFrame(advance)
  }, [target])

  useEffect(() => () => {
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current)
  }, [])

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return target
  return target.startsWith(visible) ? visible : ''
}
