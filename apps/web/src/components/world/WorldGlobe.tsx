import { useEffect, useRef } from 'react'
import createGlobe from 'cobe'

/** Ambient world context only. Evidence stays in the provenance layer, never at invented coordinates. */
export function WorldGlobe() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)')
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5)
    let globe: ReturnType<typeof createGlobe>
    let frame = 0
    let visible = false
    let last = 0
    let phi = 2.25
    try {
      const size = canvas.clientWidth * dpr
      globe = createGlobe(canvas, { width: size, height: size, devicePixelRatio: dpr, phi, theta: .18, dark: 1, diffuse: 1.65, mapSamples: 32000, mapBrightness: 6, baseColor: [.4, .51, .42], markerColor: [.74, .8, .65], glowColor: [.1, .15, .12], opacity: .94, scale: 1, markers: [] })
    } catch { return }
    function animate(now: number) {
      if (!visible || motion.matches || document.hidden) { frame = 0; return }
      if (now - last > 32) { phi += Math.min(now - last, 50) * .000035; globe.update({ phi }); last = now }
      frame = requestAnimationFrame(animate)
    }
    function start() { if (!frame && visible && !motion.matches && !document.hidden) { last = performance.now(); frame = requestAnimationFrame(animate) } }
    const intersection = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; start() })
    intersection.observe(canvas)
    const resize = new ResizeObserver(() => { const size = canvas.clientWidth * dpr; globe.update({ width: size, height: size }) })
    resize.observe(canvas)
    document.addEventListener('visibilitychange', start)
    motion.addEventListener('change', start)
    return () => { cancelAnimationFrame(frame); intersection.disconnect(); resize.disconnect(); document.removeEventListener('visibilitychange', start); motion.removeEventListener('change', start); globe.destroy() }
  }, [])
  return <div className="world-globe" aria-hidden="true"><canvas ref={canvasRef}/></div>
}
