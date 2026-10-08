import type { ReactNode } from 'react'
import { motion, useReducedMotion } from 'motion/react'

export function SpaceHeading({ index, eyebrow, title, description, children }: { index: string; eyebrow: string; title: string; description: string; children?: ReactNode }) {
  const reduced = useReducedMotion()
  return <header className="studio-heading"><div className="studio-heading-copy"><span className="studio-eyebrow"><i />{index} / {eyebrow}</span><motion.h1 initial={reduced ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .35 }}>{title}</motion.h1><p>{description}</p></div>{children && <div className="studio-heading-meta">{children}</div>}</header>
}
