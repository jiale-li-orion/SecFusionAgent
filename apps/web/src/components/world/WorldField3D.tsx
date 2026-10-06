import { useMemo, useRef } from 'react'
import { Canvas, useFrame, type ThreeEvent } from '@react-three/fiber'
import * as THREE from 'three'

type CategoryHealth = {
  category: string
  healthy: number
  degraded: number
  blocked: number
}

function SourceFlowMarkers({
  curve,
  activity,
  reduceMotion,
  dimmed,
}: {
  curve: THREE.QuadraticBezierCurve3
  activity: CategoryActivity
  reduceMotion: boolean
  dimmed: boolean
}) {
  const freshGroup = useRef<THREE.Group>(null)
  const backfillGroup = useRef<THREE.Group>(null)
  const freshCount = activity.fresh > 0 ? Math.min(8, Math.max(1, Math.ceil(Math.log2(activity.fresh + 1)))) : 0
  const backfillCount = activity.backfill > 0 ? Math.min(5, Math.max(1, Math.ceil(Math.log2(activity.backfill + 1)))) : 0

  useFrame((state) => {
    const elapsed = reduceMotion ? 0 : state.clock.elapsedTime
    freshGroup.current?.children.forEach((child, index) => {
      const t = ((index / Math.max(freshCount, 1)) + elapsed * (.12 + Math.min(activity.fresh, 1000) / 12000)) % 1
      child.position.copy(curve.getPoint(t))
    })
    backfillGroup.current?.children.forEach((child, index) => {
      const t = ((index / Math.max(backfillCount, 1)) + elapsed * .055) % 1
      child.position.copy(curve.getPoint(t))
    })
  })

  return (
    <>
      <group ref={freshGroup}>
        {Array.from({ length: freshCount }, (_, index) => (
          <mesh key={`fresh-${index}`} scale={.045 + Math.min(.045, Math.log10(activity.fresh + 1) * .012)}>
            <sphereGeometry args={[1, 8, 8]} />
            <meshBasicMaterial color="#4F94BE" transparent opacity={dimmed ? .03 : .52} depthWrite={false} />
          </mesh>
        ))}
      </group>
      <group ref={backfillGroup}>
        {Array.from({ length: backfillCount }, (_, index) => (
          <mesh key={`backfill-${index}`} scale={.038}>
            <sphereGeometry args={[1, 8, 8]} />
            <meshBasicMaterial color="#7D7AA3" transparent opacity={dimmed ? .02 : .17} depthWrite={false} />
          </mesh>
        ))}
      </group>
    </>
  )
}

type CategoryActivity = {
  fresh: number
  backfill: number
  runs: number
  observations: number
  successRate: number | null
  providerFailure: number | null
  runtimeFailure: number | null
}

function CanonicalWriteCrystallization({ canonicalWrites, reduceMotion }: { canonicalWrites: number; reduceMotion: boolean }) {
  const count = canonicalWrites <= 0 ? 0 : Math.min(18, Math.max(3, Math.ceil(Math.log2(canonicalWrites + 1) * 2.4)))
  const shards = useMemo(() => Array.from({ length: count }, (_, index) => ({
    x: 2.2 + (index % 6) * .66,
    y: ((index * 1.73) % 4.8) - 2.4,
    z: -1.05 + ((index * .61) % 1.5),
    scale: .08 + ((index * .37) % .13),
    speed: .12 + ((index * .11) % .16),
  })), [count])
  const group = useRef<THREE.Group>(null)

  useFrame((state, delta) => {
    if (!group.current || reduceMotion) return
    group.current.rotation.y = Math.sin(state.clock.elapsedTime * .16) * .035
    group.current.children.forEach((child, index) => {
      child.rotation.x += delta * (shards[index]?.speed ?? .12)
      child.rotation.y -= delta * (shards[index]?.speed ?? .12) * .8
    })
  })

  if (count === 0) return null

  return (
    <group ref={group}>
      <mesh position={[3.5, 0, -.7]} rotation={[0, 0, Math.PI / 2]}>
        <torusGeometry args={[2.7, .009, 6, 120, Math.PI * 1.22]} />
        <meshBasicMaterial color="#B9824C" transparent opacity={.13} depthWrite={false} />
      </mesh>
      <mesh position={[4.2, 0, -.95]} rotation={[0, 0, Math.PI / 2]}>
        <torusGeometry args={[3.35, .006, 6, 120, Math.PI * 1.08]} />
        <meshBasicMaterial color="#A96962" transparent opacity={.07} depthWrite={false} />
      </mesh>
      {shards.map((shard, index) => (
        <mesh key={index} position={[shard.x, shard.y, shard.z]} scale={shard.scale}>
          <octahedronGeometry args={[1, 0]} />
          <meshStandardMaterial
            color={index % 4 === 0 ? '#A96962' : '#B9824C'}
            emissive={index % 4 === 0 ? '#A96962' : '#B9824C'}
            emissiveIntensity={.08}
            metalness={.22}
            roughness={.48}
            transparent
            opacity={.52}
          />
        </mesh>
      ))}
    </group>
  )
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

const sourceLanes: Record<(typeof sourceKeys)[number], string> = {
  vulnerability: 'BUG STREAM',
  development: 'DEVELOPMENT INDEX',
  academic: 'INSIGHT CORPUS',
  vendor: 'BUG STREAM',
  independent: 'INSIGHT CORPUS',
  normative: 'INSIGHT CORPUS',
  assets: 'ASSET OBSERVATION',
  incidents: 'INCIDENT WATCH',
}

const laneFocusTargets: Record<string, { position: THREE.Vector3; lookAt: THREE.Vector3 }> = {
  'BUG STREAM': { position: new THREE.Vector3(-2.2, 1.55, 10.9), lookAt: new THREE.Vector3(-1.75, 1.35, -.25) },
  'DEVELOPMENT INDEX': { position: new THREE.Vector3(-1.8, .72, 11.1), lookAt: new THREE.Vector3(-1.35, .55, -.2) },
  'INSIGHT CORPUS': { position: new THREE.Vector3(-1.4, -.35, 11.15), lookAt: new THREE.Vector3(-1.0, -.25, -.2) },
  'INCIDENT WATCH': { position: new THREE.Vector3(-1.9, -1.7, 10.95), lookAt: new THREE.Vector3(-1.4, -1.45, -.25) },
  'ASSET OBSERVATION': { position: new THREE.Vector3(-1.5, -2.15, 10.95), lookAt: new THREE.Vector3(-1.0, -1.8, -.25) },
}

const sourcePositions = [
  new THREE.Vector3(-5.3, 3.15, -0.95),
  new THREE.Vector3(-5.0, 2.25, -1.15),
  new THREE.Vector3(-5.45, 1.35, -0.8),
  new THREE.Vector3(-5.05, .45, -1.25),
  new THREE.Vector3(-5.35, -.55, -.9),
  new THREE.Vector3(-4.95, -1.45, -1.2),
  new THREE.Vector3(-5.4, -2.35, -.85),
  new THREE.Vector3(-5.05, -3.25, -1.1),
]

export function WorldField3D({
  categories,
  categoryActivity,
  freshChanges,
  backfillObservations,
  canonicalWrites,
  focusedSource,
  focusedLane,
  focusedHot,
  reduceMotion,
  onSourceFocus,
}: {
  categories: CategoryHealth[]
  categoryActivity: Record<string, CategoryActivity>
  freshChanges: number
  backfillObservations: number
  canonicalWrites: number
  focusedSource: string | null
  focusedLane: string | null
  focusedHot: boolean
  reduceMotion: boolean
  onSourceFocus: (source: string) => void
}) {
  const health = useMemo(() => new Map(categories.map((item) => [item.category, item])), [categories])

  return (
    <div className="world-webgl" aria-hidden="true">
      <Canvas
        dpr={[1, 1.55]}
        camera={{ position: [0, 0, 12.5], fov: 43, near: .1, far: 40 }}
        gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
      >
        <fog attach="fog" args={['#dce8f1', 12, 26]} />
        <ambientLight intensity={1.7} />
        <hemisphereLight color="#F4FAFD" groundColor="#8DA7B8" intensity={1.2} />
        <directionalLight position={[-3, 5, 8]} color="#FFFFFF" intensity={2.8} />
        <pointLight position={[0, 1, 6]} color="#7EB4D4" intensity={4.8} distance={17} decay={2.1} />
        <pointLight position={[4, -3, 3]} color="#C99B6D" intensity={2.2} distance={13} decay={2.2} />
        <CameraRig focusedSource={focusedSource} focusedLane={focusedLane} focusedHot={focusedHot} reduceMotion={reduceMotion} />
        <WorldGrid reduceMotion={reduceMotion} />
        <EvidenceCore canonicalWrites={canonicalWrites} reduceMotion={reduceMotion} />
        <SourceConstellation
          health={health}
          activity={categoryActivity}
          focusedSource={focusedSource}
          focusedLane={focusedLane}
          reduceMotion={reduceMotion}
          onSourceFocus={onSourceFocus}
        />
        <ActivityParticles countFact={freshChanges} ghost={false} reduceMotion={reduceMotion} />
        <ActivityParticles countFact={backfillObservations} ghost reduceMotion={reduceMotion} />
        <CanonicalWriteCrystallization canonicalWrites={canonicalWrites} reduceMotion={reduceMotion} />
      </Canvas>
    </div>
  )
}

function CameraRig({ focusedSource, focusedLane, focusedHot, reduceMotion }: { focusedSource: string | null; focusedLane: string | null; focusedHot: boolean; reduceMotion: boolean }) {
  const target = useMemo(() => {
    if (focusedHot) {
      return {
        position: new THREE.Vector3(2.8, .15, 10.7),
        lookAt: new THREE.Vector3(2.35, -.05, -.25),
      }
    }
    if (focusedLane && laneFocusTargets[focusedLane]) return laneFocusTargets[focusedLane]
    const index = focusedSource ? sourceKeys.indexOf(focusedSource as (typeof sourceKeys)[number]) : -1
    if (index < 0) return { position: new THREE.Vector3(0, 0, 12.5), lookAt: new THREE.Vector3(0, 0, 0) }
    const source = sourcePositions[index]
    return {
      position: new THREE.Vector3(-2.4, source.y * .34, 10.8),
      lookAt: new THREE.Vector3(-2.1, source.y * .28, -.25),
    }
  }, [focusedHot, focusedLane, focusedSource])
  const currentLookAt = useRef(new THREE.Vector3(0, 0, 0))

  useFrame((state, delta) => {
    const alpha = reduceMotion ? 1 : 1 - Math.exp(-delta * 4.8)
    state.camera.position.lerp(target.position, alpha)
    currentLookAt.current.lerp(target.lookAt, alpha)
    state.camera.lookAt(currentLookAt.current)
  })

  return null
}

function WorldGrid({ reduceMotion }: { reduceMotion: boolean }) {
  const group = useRef<THREE.Group>(null)

  useFrame((state) => {
    if (reduceMotion || !group.current) return
    group.current.position.z = -1.65 + Math.sin(state.clock.elapsedTime * .16) * .035
    group.current.position.x = Math.sin(state.clock.elapsedTime * .08) * .035
  })

  return (
    <group ref={group} position={[0, 0, -1.65]}>
      <mesh position={[0, 0, -.14]}>
        <planeGeometry args={[12.8, 7.5]} />
        <meshBasicMaterial color="#AFC4D2" transparent opacity={.07} depthWrite={false} />
      </mesh>
      {[-2.8, -1.4, 0, 1.4, 2.8].map((y, index) => (
        <mesh key={`lane-${y}`} position={[0, y, 0]}>
          <boxGeometry args={[12.4, index === 2 ? .014 : .007, .008]} />
          <meshBasicMaterial color={index === 2 ? '#679AB8' : '#8FAABD'} transparent opacity={index === 2 ? .16 : .07} depthWrite={false} />
        </mesh>
      ))}
      {[-4.2, -2.8, -1.4, 0, 1.4, 2.8, 4.2].map((x, index) => (
        <mesh key={`cross-${x}`} position={[x, 0, 0]}>
          <boxGeometry args={[.006, 7.2, .008]} />
          <meshBasicMaterial color={index === 3 ? '#777C9E' : '#719BB5'} transparent opacity={index === 3 ? .09 : .045} depthWrite={false} />
        </mesh>
      ))}
      {[-3.8, -2.3, -.8, .8, 2.3, 3.8].map((x, index) => (
        <mesh key={`checkpoint-${x}`} position={[x, 0, .02]}>
          <boxGeometry args={[.018, 6.5, .012]} />
          <meshBasicMaterial color={index < 3 ? '#709AB2' : '#B58A5D'} transparent opacity={.035 + index * .004} depthWrite={false} />
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
          color="#DCEAF2"
          emissive="#79A8C4"
          emissiveIntensity={.06 + energy * .14}
          metalness={.18}
          roughness={.42}
          transparent
          opacity={.93}
        />
      </mesh>
      <mesh scale={1.17}>
        <icosahedronGeometry args={[1.05, 2]} />
        <meshBasicMaterial color="#5F89A3" wireframe transparent opacity={.34} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[1.42, .015, 8, 128]} />
        <meshBasicMaterial color="#5F91AF" transparent opacity={.34} />
      </mesh>
      <mesh rotation={[Math.PI / 2.4, .45, .2]}>
        <torusGeometry args={[1.78, .009, 8, 128]} />
        <meshBasicMaterial color="#7A7698" transparent opacity={.16} />
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
      <meshBasicMaterial color="#7EA570" transparent opacity={.16} depthWrite={false} />
    </mesh>
  )
}

function SourceConstellation({
  health,
  activity,
  focusedSource,
  focusedLane,
  reduceMotion,
  onSourceFocus,
}: {
  health: Map<string, CategoryHealth>
  activity: Record<string, CategoryActivity>
  focusedSource: string | null
  focusedLane: string | null
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
        const color = blockedRatio > .25 ? '#B76767' : degradedRatio > .12 ? '#B9844E' : total ? '#4F89B0' : '#83939C'
        const selected = focusedSource === key
        const laneSelected = focusedLane === sourceLanes[key]
        const dimmed = Boolean((focusedSource && !selected) || (focusedLane && !laneSelected))
        const runtimeActivity = activity[key] ?? {
          fresh: 0,
          backfill: 0,
          runs: 0,
          observations: 0,
          successRate: null,
          providerFailure: null,
          runtimeFailure: null,
        }
        return (
          <SourceNode
            key={key}
            sourceKey={key}
            index={index}
            position={sourcePositions[index]}
            color={color}
            degraded={Boolean(status?.degraded)}
            blocked={Boolean(status?.blocked && status.blocked === total)}
            activity={runtimeActivity}
            selected={selected || laneSelected}
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
  activity,
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
  activity: CategoryActivity
  selected: boolean
  dimmed: boolean
  reduceMotion: boolean
  onFocus: () => void
}) {
  const node = useRef<THREE.Group>(null)
  const providerFailure = activity.providerFailure ?? 0
  const runtimeFailure = activity.runtimeFailure ?? 0
  const failureRate = Math.max(providerFailure, runtimeFailure)
  const curve = useMemo(() => new THREE.QuadraticBezierCurve3(
      position,
      position.clone().multiplyScalar(.42).add(new THREE.Vector3(0, 0, 1.4)),
      new THREE.Vector3(0, 0, 0),
    ), [position])
  const path = useMemo(() => {
    return new THREE.BufferGeometry().setFromPoints(curve.getPoints(42))
  }, [curve])
  const pathLine = useMemo(
    () => new THREE.Line(
      path,
      new THREE.LineBasicMaterial({
        color: selected ? '#6D9567' : '#6E9AB4',
        transparent: true,
        opacity: dimmed ? .02 : selected ? .42 : activity.fresh > 0 || activity.runs > 0 ? .19 : .08,
      }),
    ),
    [activity.fresh, activity.runs, dimmed, path, selected],
  )

  useFrame((state, delta) => {
    if (!node.current || reduceMotion) return
    node.current.rotation.y += delta * (.13 + index * .005)
    node.current.rotation.z -= delta * .035
    if (failureRate > 0 && !blocked) {
      const cadence = 2.2 + Math.min(3.8, failureRate * 8)
      const instability = .035 + Math.min(.09, failureRate * .16)
      const pulse = .98 + Math.sin(state.clock.elapsedTime * cadence + index) * instability
      node.current.scale.setScalar(selected ? pulse * 1.18 : pulse)
    } else if (activity.runs > 0 && !blocked) {
      const successfulRuns = activity.runs * (activity.successRate ?? 1)
      const cadence = Math.min(4.2, 1.25 + Math.log2(successfulRuns + 1) * .55)
      const pulse = .96 + Math.abs(Math.sin(state.clock.elapsedTime * cadence + index)) * .13
      node.current.scale.setScalar(selected ? pulse * 1.18 : pulse)
    } else if (degraded && !blocked) {
      const flicker = .96 + Math.abs(Math.sin(state.clock.elapsedTime * 1.7 + index)) * .06
      node.current.scale.setScalar(selected ? flicker * 1.18 : flicker)
    } else {
      node.current.scale.setScalar(selected ? 1.18 : 1)
    }
  })

  return (
    <group>
      <primitive object={pathLine} />
      <SourceFlowMarkers curve={curve} activity={activity} reduceMotion={reduceMotion} dimmed={dimmed} />
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
            emissiveIntensity={blocked ? .01 : selected ? .20 : .07}
            metalness={.18}
            roughness={.44}
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
          <meshBasicMaterial color="#7B7798" transparent opacity={dimmed ? .018 : .10} />
        </mesh>
        {providerFailure > 0 && (
          <mesh rotation={[Math.PI / 2.15, .08, Math.PI / 5]}>
            <torusGeometry args={[.72, .012, 6, 72]} />
            <meshBasicMaterial color="#B9844E" transparent opacity={dimmed ? .02 : Math.min(.44, .12 + providerFailure * .9)} depthWrite={false} />
          </mesh>
        )}
        {runtimeFailure > 0 && (
          <mesh rotation={[Math.PI / 2.7, .42, -.18]}>
            <torusGeometry args={[.83, .009, 6, 72]} />
            <meshBasicMaterial color="#A96962" transparent opacity={dimmed ? .018 : Math.min(.38, .10 + runtimeFailure * .82)} depthWrite={false} />
          </mesh>
        )}
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
        color={ghost ? '#7C8790' : '#5B92B4'}
        size={ghost ? .035 : .052}
        sizeAttenuation
        transparent
        opacity={ghost ? .20 : .52}
        depthWrite={false}
      />
    </points>
  )
}
