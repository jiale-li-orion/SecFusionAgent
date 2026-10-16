import { useEffect, useRef } from 'react'
import { developingFragment, developingVertex } from '../../lib/developingShader'
import { developingProfiles, type DevelopingVariant } from '../../lib/developingProfiles'

type Props = {
  className?: string
  variant?: DevelopingVariant
}

/** An ambient material study, never a measurement or an indication that an agent is running. */
export function DevelopingField({ className = '', variant = 'question' }: Props) {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const scope = canvas.closest('[data-develop-scope]') ?? canvas.parentElement!
    const reduced = matchMedia('(prefers-reduced-motion: reduce)')
    const coarse = matchMedia('(pointer: coarse)')
    const gl = canvas.getContext('webgl', { alpha: true, antialias: false, premultipliedAlpha: false, depth: false, powerPreference: 'low-power' })
    if (!gl) { canvas.dataset.renderer = 'fallback'; return }

    function compile(type: number, source: string) {
      const shader = gl!.createShader(type)!
      gl!.shaderSource(shader, source)
      gl!.compileShader(shader)
      if (!gl!.getShaderParameter(shader, gl!.COMPILE_STATUS)) { gl!.deleteShader(shader); return null }
      return shader
    }
    const vertex = compile(gl.VERTEX_SHADER, developingVertex)
    const fragment = compile(gl.FRAGMENT_SHADER, developingFragment)
    const program = gl.createProgram()!
    if (!vertex || !fragment) {
      if (vertex) gl.deleteShader(vertex)
      if (fragment) gl.deleteShader(fragment)
      gl.deleteProgram(program)
      canvas.dataset.renderer = 'fallback'
      return
    }
    gl.attachShader(program, vertex); gl.attachShader(program, fragment); gl.linkProgram(program)
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      gl.deleteShader(vertex); gl.deleteShader(fragment); gl.deleteProgram(program)
      canvas.dataset.renderer = 'fallback'
      return
    }
    gl.useProgram(program)
    const buffer = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW)
    const position = gl.getAttribLocation(program, 'position')
    gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0)
    const uniform = Object.fromEntries(['resolution', 'time', 'arrival', 'focus', 'direction', 'impulse', 'variant'].map(name => [name, gl.getUniformLocation(program, name)]))
    canvas.dataset.renderer = 'webgl'
    let frame = 0, previous = 0, elapsed = 0, entered = 0
    let focus = 0, targetFocus = 0, direction = 0, targetDirection = 0, impulse = 0
    let visible = true, disposed = false, lost = false
    const composition = developingProfiles[variant]
    gl.uniform1f(uniform.variant, composition.seed)
    ;['depositLeft', 'depositMiddle', 'depositRight'].forEach((name, index) => {
      gl.uniform4fv(gl.getUniformLocation(program, name), composition.deposits[index])
    })
    gl.uniform4fv(gl.getUniformLocation(program, 'motion'), composition.motion)
    gl.uniform2fv(gl.getUniformLocation(program, 'origin'), composition.origin)
    function paint() {
      if (disposed || lost) return
      gl!.uniform2f(uniform.resolution, canvas!.width, canvas!.height)
      gl!.uniform1f(uniform.time, reduced.matches ? 0 : elapsed)
      gl!.uniform1f(uniform.arrival, reduced.matches ? 1.8 : Math.min(1.8, entered / 1.6))
      gl!.uniform1f(uniform.focus, focus)
      gl!.uniform1f(uniform.direction, direction)
      gl!.uniform1f(uniform.impulse, reduced.matches ? 0 : impulse)
      gl!.drawArrays(gl!.TRIANGLES, 0, 6)
    }
    function tick(now: number) {
      frame = 0
      if (disposed || lost || document.hidden || !visible || reduced.matches) return
      if (!previous) previous = now
      const delta = now - previous
      if (delta >= (coarse.matches ? 1000 / 24 : 1000 / 30)) {
        const dt = Math.min(delta / 1000, .08)
        previous = now; elapsed += dt; entered += dt
        const damping = 1 - Math.exp(-dt * 4.5)
        focus += (targetFocus - focus) * damping
        direction += (targetDirection - direction) * damping
        impulse *= Math.exp(-dt * 1.8)
        paint()
      }
      frame = requestAnimationFrame(tick)
    }
    function resume() {
      cancelAnimationFrame(frame); frame = 0; previous = 0
      if (disposed || lost || document.hidden || !visible) return
      if (reduced.matches) { focus = targetFocus; direction = targetDirection; paint() }
      else frame = requestAnimationFrame(tick)
    }
    function resize() {
      const bounds = canvas!.getBoundingClientRect()
      const scale = Math.min(devicePixelRatio || 1, 1.5, 1200 / Math.max(bounds.width, 1))
      canvas!.width = Math.max(1, Math.round(bounds.width * scale))
      canvas!.height = Math.max(1, Math.round(bounds.height * scale))
      gl!.viewport(0, 0, canvas!.width, canvas!.height)
      paint(); resume()
    }
    function respond(target: EventTarget | null, burst = false) {
      if (!(target instanceof Element)) return
      const control = target.closest('button, a, input, textarea, [role=tab]')
      const starter = target.closest('.qa-starter-item')
      targetFocus = target.matches('input, textarea') || starter ? 1 : control ? .65 : 0
      if (starter) targetDirection = [...scope.querySelectorAll('.qa-starter-item')].indexOf(starter) - 1
      else if (control) {
        const bounds = scope.getBoundingClientRect(), box = control.getBoundingClientRect()
        targetDirection = Math.max(-1, Math.min(1, (box.x + box.width / 2 - bounds.x) / Math.max(bounds.width, 1) * 2 - 1))
      } else targetDirection = 0
      if (burst && !reduced.matches) impulse = 1
      if (reduced.matches) { focus = targetFocus; direction = targetDirection; paint() }
    }
    const onFocus = (event: Event) => respond(event.target, true)
    const onInput = (event: Event) => respond(event.target, true)
    const onOver = (event: Event) => {
      const pointer = event as PointerEvent
      if (pointer.pointerType !== 'mouse') return
      const target = pointer.target instanceof Element ? pointer.target.closest('button, a, input, textarea, [role=tab]') : null
      const from = pointer.relatedTarget instanceof Element ? pointer.relatedTarget.closest('button, a, input, textarea, [role=tab]') : null
      if (target && target !== from) respond(target, true)
    }
    const onOut = (event: Event) => {
      const active = document.activeElement
      if (event.type === 'pointerout' && active instanceof Element && scope.contains(active) && active.matches('input, textarea')) { respond(active); return }
      const related = (event as FocusEvent).relatedTarget
      if (related instanceof Element && scope.contains(related)) respond(related)
      else { targetFocus = 0; targetDirection = 0; if (reduced.matches) { focus = 0; direction = 0; paint() } }
    }
    const onContextLost = (event: Event) => { event.preventDefault(); lost = true; cancelAnimationFrame(frame); canvas.dataset.renderer = 'fallback' }
    const observer = new IntersectionObserver(entries => { visible = entries[0]?.isIntersecting ?? false; resume() })
    const resizeObserver = new ResizeObserver(resize)
    observer.observe(canvas); resizeObserver.observe(canvas)
    scope.addEventListener('focusin', onFocus); scope.addEventListener('focusout', onOut)
    scope.addEventListener('input', onInput); scope.addEventListener('pointerover', onOver)
    scope.addEventListener('click', onFocus)
    scope.addEventListener('pointerout', onOut)
    document.addEventListener('visibilitychange', resume); reduced.addEventListener('change', resume)
    canvas.addEventListener('webglcontextlost', onContextLost)
    resize()
    return () => {
      disposed = true; cancelAnimationFrame(frame); observer.disconnect(); resizeObserver.disconnect()
      scope.removeEventListener('focusin', onFocus); scope.removeEventListener('focusout', onOut)
      scope.removeEventListener('input', onInput); scope.removeEventListener('pointerover', onOver)
      scope.removeEventListener('click', onFocus)
      scope.removeEventListener('pointerout', onOut)
      document.removeEventListener('visibilitychange', resume); reduced.removeEventListener('change', resume)
      canvas.removeEventListener('webglcontextlost', onContextLost)
      gl.deleteBuffer(buffer); gl.deleteShader(vertex); gl.deleteShader(fragment); gl.deleteProgram(program)
    }
  }, [variant])
  return <canvas ref={ref} className={`developing-field ${className}`} data-composition={variant} aria-hidden="true" />
}
