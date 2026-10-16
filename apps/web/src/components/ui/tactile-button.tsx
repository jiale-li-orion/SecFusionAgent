import { useRef } from 'react'
import { motion, useReducedMotion, useSpring, type HTMLMotionProps } from 'motion/react'

/** Small pointer displacement; the resting layout and native button behavior stay intact. */
export function TactileButton({ onPointerEnter, onPointerMove, onPointerLeave, onBlur, ...props }: HTMLMotionProps<'button'>) {
  const reducedMotion = useReducedMotion()
  const bounds = useRef<DOMRect | null>(null)
  const x = useSpring(0, { stiffness: 290, damping: 20, mass: .55 })
  const y = useSpring(0, { stiffness: 290, damping: 20, mass: .55 })
  const reset = () => { bounds.current = null; x.set(0); y.set(0) }

  return <motion.button {...props}
    style={{ ...props.style, x: reducedMotion ? 0 : x, y: reducedMotion ? 0 : y }}
    whileTap={reducedMotion ? undefined : { scale: .985 }}
    onPointerEnter={event => {
      if (!reducedMotion && event.pointerType === 'mouse') bounds.current = event.currentTarget.getBoundingClientRect()
      onPointerEnter?.(event)
    }}
    onPointerMove={event => {
      const rect = bounds.current
      if (!reducedMotion && event.pointerType === 'mouse' && rect) {
        x.set(Math.max(-1, Math.min(1, (event.clientX - rect.x) / rect.width * 2 - 1)) * 5)
        y.set(Math.max(-1, Math.min(1, (event.clientY - rect.y) / rect.height * 2 - 1)) * 4)
      }
      onPointerMove?.(event)
    }}
    onPointerLeave={event => { reset(); onPointerLeave?.(event) }}
    onBlur={event => { reset(); onBlur?.(event) }}
  />
}
