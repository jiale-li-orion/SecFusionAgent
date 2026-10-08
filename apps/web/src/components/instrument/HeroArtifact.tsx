import { useEffect, useRef } from 'react'
import { useReducedMotion } from 'motion/react'
import { artifactFragment, artifactVertex } from './artifactShader'
import { RoleSigil } from './RoleSigil'
import { SourceArtwork } from './SourceArtwork'

const models: Record<string, number> = {
  DecisionRole: 0, vendor: 0, InvestigationRole: 1, independent: 1,
  EnrichmentRole: 2, academic: 2, normative: 2, development: 3, assets: 4,
}

/** Material identity only. Motion never signals a source, task or write event. */
export function HeroArtifact({ kind }: { kind: string }) {
  const ref = useRef<HTMLCanvasElement>(null)
  const reduced = useReducedMotion()
  const model = models[kind] ?? 5
  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const gl = canvas.getContext('webgl', { alpha: true, antialias: true, premultipliedAlpha: false })
    if (!gl) return
    const compile = (type: number, source: string) => {
      const shader = gl.createShader(type)
      if (!shader) return null
      gl.shaderSource(shader, source)
      gl.compileShader(shader)
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        gl.deleteShader(shader)
        return null
      }
      return shader
    }
    const vertex = compile(gl.VERTEX_SHADER, artifactVertex)
    const fragment = compile(gl.FRAGMENT_SHADER, artifactFragment)
    if (!vertex || !fragment) {
      if (vertex) gl.deleteShader(vertex)
      if (fragment) gl.deleteShader(fragment)
      return
    }
    const program = gl.createProgram()
    if (!program) { gl.deleteShader(vertex); gl.deleteShader(fragment); return }
    gl.attachShader(program, vertex)
    gl.attachShader(program, fragment)
    gl.linkProgram(program)
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      gl.deleteProgram(program); gl.deleteShader(vertex); gl.deleteShader(fragment)
      return
    }
    gl.useProgram(program)
    const buffer = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]), gl.STATIC_DRAW)
    const attribute = gl.getAttribLocation(program, 'position')
    gl.enableVertexAttribArray(attribute)
    gl.vertexAttribPointer(attribute, 2, gl.FLOAT, false, 0, 0)
    const size = gl.getUniformLocation(program, 'resolution')
    const clock = gl.getUniformLocation(program, 'time')
    const type = gl.getUniformLocation(program, 'model')
    const pointer = gl.getUniformLocation(program, 'pointer')
    let frame = 0, visible = true, last = -100, lost = false
    let elapsed = 0, previous = performance.now()
    const target = [0, 0], current = [0, 0]
    const draw = () => {
      gl.uniform1f(clock, reduced ? 0 : elapsed)
      gl.uniform1f(type, model)
      gl.uniform2f(pointer, current[0], current[1])
      gl.drawArrays(gl.TRIANGLES, 0, 6)
      canvas.dataset.ready = 'true'
    }
    const resize = () => {
      const rect = canvas.getBoundingClientRect()
      if (!rect.width || !rect.height) return
      const scale = Math.min(window.devicePixelRatio || 1, 1.5, 720 / rect.width, 480 / rect.height)
      canvas.width = Math.max(1, Math.round(rect.width * scale))
      canvas.height = Math.max(1, Math.round(rect.height * scale))
      gl.viewport(0, 0, canvas.width, canvas.height)
      gl.uniform2f(size, canvas.width, canvas.height)
      if (visible && !lost) draw()
    }
    const render = (now: number) => {
      if (visible && document.visibilityState === 'visible') elapsed += Math.min((now - previous) / 1000, .12)
      if (!lost && visible && document.visibilityState === 'visible' && now - last > 80) {
        current[0] += (target[0] - current[0]) * .12
        current[1] += (target[1] - current[1]) * .12
        draw()
        last = now
      }
      previous = now
      if (!reduced && !lost) frame = requestAnimationFrame(render)
    }
    const move = (event: PointerEvent) => {
      if (reduced || event.pointerType === 'touch') return
      const rect = canvas.getBoundingClientRect()
      target[0] = (event.clientX - rect.left) / rect.width * 2 - 1
      target[1] = (event.clientY - rect.top) / rect.height * 2 - 1
    }
    const leave = () => { target[0] = 0; target[1] = 0 }
    const contextLost = () => {
      lost = true
      cancelAnimationFrame(frame)
      delete canvas.dataset.ready
    }
    canvas.addEventListener('pointermove', move, { passive: true })
    canvas.addEventListener('pointerleave', leave)
    canvas.addEventListener('webglcontextlost', contextLost)
    const observer = new ResizeObserver(resize)
    const intersection = new IntersectionObserver(entries => {
      visible = entries[0]?.isIntersecting ?? false
      if (visible && reduced && !lost) draw()
    })
    observer.observe(canvas)
    intersection.observe(canvas)
    resize()
    if (!reduced) frame = requestAnimationFrame(render)
    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect(); intersection.disconnect()
      canvas.removeEventListener('pointermove', move)
      canvas.removeEventListener('pointerleave', leave)
      canvas.removeEventListener('webglcontextlost', contextLost)
      delete canvas.dataset.ready
      gl.deleteBuffer(buffer); gl.deleteProgram(program)
      gl.deleteShader(vertex); gl.deleteShader(fragment)
    }
  }, [model, reduced])
  return <div className={'hero-artifact artifact-' + kind} aria-hidden="true">
    <div className="artifact-fallback">{kind.endsWith('Role')
      ? <RoleSigil role={kind} live={false} />
      : <SourceArtwork category={kind} index={0} fit="meet" />}</div>
    <canvas ref={ref} />
  </div>
}
