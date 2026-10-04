import { useMemo, useRef } from 'react'
import { Canvas, useFrame, type ThreeEvent } from '@react-three/fiber'
import * as THREE from 'three'

type CategoryHealth = {
  category: string
  healthy: number
  degraded: number
  blocked: number
}

const sourceKeys = [
  'vulnerability',
  'development',
  'academic',
  'vendor',
  'independent',
  'normative',
  'assets',
  'incidents',
] as const

const sourcePositions = [
  new THREE.Vector3(-4.7, 2.55, -0.8),
  new THREE.Vector3(-2.0, 3.55, -1.3),
  new THREE.Vector3(1.5, 3.65, -1.0),
  new THREE.Vector3(4.5, 2.55, -0.6),
  new THREE.Vector3(4.8, -1.9, -0.7),
  new THREE.Vector3(1.75, -3.35, -1.15),
  new THREE.Vector3(-1.8, -3.45, -1.1),
  new THREE.Vector3(-4.7, -1.75, -0.7),
]

export function WorldField3D({
  categories,
  freshChanges,
  backfillObservations,
  canonicalWrites,
  focusedSource,
  reduceMotion,
  onSourceFocus,
}: {
  categories: CategoryHealth[]
  freshChanges: number
  backfillObservations: number
  canonicalWrites: number
  focusedSource: string | null
  reduceMotion: boolean
  onSourceFocus: (source: string) => void
}) {
  const health = useMemo(() => new Map(categories.map((item) => [item.category, item])), [categories])

  return (
    <div className="world-webgl-v3" aria-hidden="true">
      <Canvas
        dpr={[1, 1.55]}
        camera={{ position: [0, 0, 12.5], fov: 43, near: .1, far: 40 }}
        gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
      >
        <fog attach="fog" args={['#07090D', 11, 26]} />
        <ambientLight intensity={0.42} />
        <pointLight position={[0, 0, 5]} color="#72D7FF" intensity={18} distance={16} decay={2.1} />
        <pointLight position={[4, -3, 2]} color="#A88BFF" intensity={8} distance={13} decay={2.2} />
        <WorldGrid reduceMotion={reduceMotion} />
        <EvidenceCore canonicalWrites={canonicalWrites} reduceMotion={reduceMotion} />
        <SourceConstellation
          health={health}
          focusedSource={focusedSource}
          reduceMotion={reduceMotion}
          onSourceFocus={onSourceFocus}
        />
        <ActivityParticles countFact={freshChanges} ghost={false} reduceMotion={reduceMotion} />
        <ActivityParticles countFact={backfillObservations} ghost reduceMotion={reduceMotion} />
      </Canvas>
    </div>
  )
}

function WorldGrid({ reduceMotion }: { reduceMotion: boolean }) {
  const group = useRef<THREE.Group>(null)

  useFrame((state, delta) => {
    if (reduceMotion || !group.current) return
    group.current.rotation.z += delta * .006
    group.current.position.x = Math.sin(state.clock.elapsedTime * .08) * .06
  })

  return (
    <group ref={group} rotation={[1.16, 0, 0]}>
      {[3.1, 4.7, 6.25].map((radius, index) => (
        <mesh key={radius}>
          <torusGeometry args={[radius, index === 1 ? .012 : .008, 8, 180]} />
          <meshBasicMaterial
            color={index === 1 ? '#72D7FF' : '#A88BFF'}
            transparent
            opacity={index === 1 ? .12 : .065}
            depthWrite={false}
          />
        </mesh>
      ))}
      {Array.from({ length: 12 }, (_, index) => (
        <mesh key={index} rotation={[0, 0, (index / 12) * Math.PI * 2]}>
          <boxGeometry args={[12.6, .006, .006]} />
          <meshBasicMaterial color="#72D7FF" transparent opacity={.025} depthWrite={false} />
        </mesh>
      ))}
    </group>
  )
}

function EvidenceCore({ canonicalWrites, reduceMotion }: { canonicalWrites: number; reduceMotion: boolean }) {
  const group = useRef<THREE.Group>(null)
  const energy = Math.min(1, Math.log10(canonicalWrites + 1) / 2.3)

  useFrame((state, delta) => {
    if (!group.current) return
    if (!reduceMotion) {
      group.current.rotation.y += delta * .065
      group.current.rotation.x = .18 + Math.sin(state.clock.elapsedTime * .22) * .04
    }
  })

  return (
    <group ref={group}>
      <mesh>
        <icosahedronGeometry args={[1.05, 2]} />
        <meshStandardMaterial
          color="#112633"
          emissive="#72D7FF"
          emissiveIntensity={.18 + energy * .34}
          metalness={.62}
          roughness={.28}
          transparent
          opacity={.93}
        />
      </mesh>
      <mesh scale={1.17}>
        <icosahedronGeometry args={[1.05, 2]} />
        <meshBasicMaterial color="#72D7FF" wireframe transparent opacity={.26} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[1.42, .015, 8, 128]} />
        <meshBasicMaterial color="#72D7FF" transparent opacity={.28} />
      </mesh>
      <mesh rotation={[Math.PI / 2.4, .45, .2]}>
        <torusGeometry args={[1.78, .009, 8, 128]} />
        <meshBasicMaterial color="#A88BFF" transparent opacity={.13} />
      </mesh>
      {canonicalWrites > 0 && (
        <CoreWritePulse reduceMotion={reduceMotion} />
      )}
    </group>
  )
}

function CoreWritePulse({ reduceMotion }: { reduceMotion: boolean }) {
  const pulse = useRef<THREE.Mesh>(null)

  useFrame((state) => {
    if (!pulse.current || reduceMotion) return
    const phase = (state.clock.elapsedTime * .32) % 1
    pulse.current.scale.setScalar(1 + phase * .85)
    const material = pulse.current.material as THREE.MeshBasicMaterial
    material.opacity = (1 - phase) * .16
  })

  return (
    <mesh ref={pulse} rotation={[Math.PI / 2, 0, 0]}>
      <torusGeometry args={[1.7, .014, 8, 128]} />
      <meshBasicMaterial color="#C9F45B" transparent opacity={.12} depthWrite={false} />
    </mesh>
  )
}

function SourceConstellation({
  health,
  focusedSource,
  reduceMotion,
  onSourceFocus,
}: {
  health: Map<string, CategoryHealth>
  focusedSource: string | null
  reduceMotion: boolean
  onSourceFocus: (source: string) => void
}) {
  return (
    <group>
      {sourceKeys.map((key, index) => {
        const status = health.get(key)
        const total = status ? status.healthy + status.degraded + status.blocked : 0
        const blockedRatio = total ? (status?.blocked ?? 0) / total : 0
        const degradedRatio = total ? (status?.degraded ?? 0) / total : 0
        const color = blockedRatio > .25 ? '#FF6B72' : degradedRatio > .12 ? '#FFB35C' : total ? '#72D7FF' : '#59656D'
        const selected = focusedSource === key
        const dimmed = Boolean(focusedSource && !selected)
        return (
          <SourceNode
            key={key}
            sourceKey={key}
            index={index}
            position={sourcePositions[index]}
            color={color}
            degraded={Boolean(status?.degraded)}
            blocked={Boolean(status?.blocked && status.blocked === total)}
            selected={selected}
            dimmed={dimmed}
            reduceMotion={reduceMotion}
            onFocus={() => onSourceFocus(key)}
          />
        )
      })}
    </group>
  )
}

function SourceNode({
  sourceKey,
  index,
  position,
  color,
  degraded,
  blocked,
  selected,
  dimmed,
  reduceMotion,
  onFocus,
}: {
  sourceKey: string
  index: number
  position: THREE.Vector3
  color: string
  degraded: boolean
  blocked: boolean
  selected: boolean
  dimmed: boolean
  reduceMotion: boolean
  onFocus: () => void
}) {
  const node = useRef<THREE.Group>(null)
  const path = useMemo(() => {
    const curve = new THREE.QuadraticBezierCurve3(
      position,
      position.clone().multiplyScalar(.42).add(new THREE.Vector3(0, 0, 1.4)),
      new THREE.Vector3(0, 0, 0),
    )
    return new THREE.BufferGeometry().setFromPoints(curve.getPoints(42))
  }, [position])
  const pathLine = useMemo(
    () => new THREE.Line(
      path,
      new THREE.LineBasicMaterial({
        color: selected ? '#C9F45B' : '#72D7FF',
        transparent: true,
        opacity: dimmed ? .025 : selected ? .48 : .09,
      }),
    ),
    [dimmed, path, selected],
  )

  useFrame((state, delta) => {
    if (!node.current || reduceMotion) return
    node.current.rotation.y += delta * (.13 + index * .005)
    node.current.rotation.z -= delta * .035
    if (degraded && !blocked) {
      const pulse = .94 + Math.abs(Math.sin(state.clock.elapsedTime * 2.2 + index)) * .12
      node.current.scale.setScalar(selected ? pulse * 1.18 : pulse)
    } else {
      node.current.scale.setScalar(selected ? 1.18 : 1)
    }
  })

  return (
    <group>
      <primitive object={pathLine} />
      <group
        ref={node}
        position={position}
        onPointerDown={(event: ThreeEvent<PointerEvent>) => {
          event.stopPropagation()
          onFocus()
        }}
      >
        <mesh>
          <octahedronGeometry args={[selected ? .31 : .25, 0]} />
          <meshStandardMaterial
            color={color}
            emissive={color}
            emissiveIntensity={blocked ? .02 : selected ? .72 : .28}
            metalness={.48}
            roughness={.32}
            transparent
            opacity={dimmed ? .12 : blocked ? .23 : .9}
          />
        </mesh>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[.44, .011, 6, 70]} />
          <meshBasicMaterial color={color} transparent opacity={dimmed ? .03 : selected ? .52 : .18} />
        </mesh>
        <mesh rotation={[Math.PI / 2, 0, Math.PI / 3]}>
          <torusGeometry args={[.59, .007, 6, 70]} />
          <meshBasicMaterial color="#A88BFF" transparent opacity={dimmed ? .02 : .08} />
        </mesh>
        <mesh visible={false} name={sourceKey}>
          <sphereGeometry args={[.65, 10, 10]} />
          <meshBasicMaterial transparent opacity={0} />
        </mesh>
      </group>
    </group>
  )
}

function ActivityParticles({
  countFact,
  ghost,
  reduceMotion,
}: {
  countFact: number
  ghost: boolean
  reduceMotion: boolean
}) {
  const visualCount = countFact <= 0 ? 0 : Math.min(58, Math.max(4, Math.ceil(Math.log2(countFact + 1) * (ghost ? 2.7 : 5.2))))
  const points = useRef<THREE.Points>(null)

  const state = useMemo(() => {
    const positions = new Float32Array(visualCount * 3)
    const sourceIndex = new Uint8Array(visualCount)
    const offset = new Float32Array(visualCount)
    const seed = new Float32Array(visualCount)

    for (let index = 0; index < visualCount; index += 1) {
      sourceIndex[index] = index % sourcePositions.length
      offset[index] = ((index * 0.61803398875) % 1)
      seed[index] = ((index * 0.38196601125) % 1) - .5
    }
    return { positions, sourceIndex, offset, seed }
  }, [visualCount])

  useFrame((frame) => {
    if (!points.current || visualCount === 0) return
    const positionAttribute = points.current.geometry.getAttribute('position') as THREE.BufferAttribute
    const elapsed = reduceMotion ? 0 : frame.clock.elapsedTime
    const speed = ghost ? .035 : .105

    for (let index = 0; index < visualCount; index += 1) {
      const origin = sourcePositions[state.sourceIndex[index]]
      const t = reduceMotion ? state.offset[index] : (state.offset[index] + elapsed * speed) % 1
      const inv = 1 - t
      const bend = Math.sin(t * Math.PI) * (ghost ? .35 : .58)
      const x = origin.x * inv + state.seed[index] * bend
      const y = origin.y * inv + Math.cos(index * 1.7) * bend * .22
      const z = origin.z * inv + bend * (ghost ? -.6 : 1.05)
      positionAttribute.setXYZ(index, x, y, z)
    }
    positionAttribute.needsUpdate = true
  })

  if (visualCount === 0) return null

  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[state.positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        color={ghost ? '#6C7782' : '#72D7FF'}
        size={ghost ? .035 : .052}
        sizeAttenuation
        transparent
        opacity={ghost ? .24 : .66}
        depthWrite={false}
      />
    </points>
  )
}
