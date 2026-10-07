import { useEffect, useMemo, useRef } from 'react'
import { useFrame, type ThreeEvent } from '@react-three/fiber'
import * as THREE from 'three'
import type { IncidentSummary } from '../../lib/api'

type OrbitPoint = {
  incident: IncidentSummary
  candidate: THREE.Vector3
  durable: THREE.Vector3
  color: string
  scale: number
}

function stablePhase(value: string) {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0) / 0xffffffff * Math.PI * 2
}

function incidentTone(lifecycle: string) {
  const state = lifecycle.toLowerCase()
  if (state.includes('resolv') || state.includes('clos')) return '#739879'
  if (state.includes('watch') || state.includes('monitor')) return '#B9824C'
  if (state.includes('block') || state.includes('fail')) return '#A96962'
  return '#8A7BA0'
}

function buildOrbit(incidents: IncidentSummary[]): OrbitPoint[] {
  return incidents.slice(0, 7).map((incident, index) => {
    const phase = stablePhase(incident.incident_id) + index * .31
    const candidateRadius = 1.03 + (index % 2) * .11
    const durableRadius = .48 + Math.min(.18, incident.source_diversity_count * .028)
    return {
      incident,
      candidate: new THREE.Vector3(
        Math.cos(phase) * candidateRadius,
        Math.sin(phase) * candidateRadius,
        .02 + (index % 3) * .035,
      ),
      durable: new THREE.Vector3(
        Math.cos(phase + .2) * durableRadius,
        Math.sin(phase + .2) * durableRadius,
        .12 + (index % 2) * .045,
      ),
      color: incidentTone(incident.lifecycle),
      scale: .082 + Math.min(.055, Math.log2(Math.max(1, incident.current_revision) + 1) * .014),
    }
  })
}

export function DurableIncidentOrbit({ incidents, reduceMotion, onOpen }: { incidents: IncidentSummary[]; reduceMotion: boolean; onOpen: (incidentId: string) => void }) {
  const group = useRef<THREE.Group>(null)
  const points = useMemo(() => buildOrbit(incidents), [incidents])
  const promotionLines = useMemo(() => points.map((point) => new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([
      point.candidate,
      point.candidate.clone().lerp(point.durable, .42).add(new THREE.Vector3(0, 0, .2)),
      point.durable,
    ]),
    new THREE.LineBasicMaterial({ color: point.color, transparent: true, opacity: .16 }),
  )), [points])

  useEffect(() => () => {
    promotionLines.forEach((line) => {
      line.geometry.dispose()
      ;(line.material as THREE.Material).dispose()
    })
  }, [promotionLines])

  useFrame((state) => {
    if (!group.current || reduceMotion || points.length === 0) return
    group.current.rotation.z = Math.sin(state.clock.elapsedTime * .16) * .025
    group.current.rotation.y = Math.sin(state.clock.elapsedTime * .11) * .06
  })

  if (points.length === 0) return null

  return (
    <group ref={group} position={[1.6, -2.05, -.35]}>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[1.08, .009, 6, 96]} />
        <meshBasicMaterial color="#8D7899" transparent opacity={.10} depthWrite={false} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[.62, .014, 6, 96]} />
        <meshBasicMaterial color="#B9824C" transparent opacity={.20} depthWrite={false} />
      </mesh>

      {points.map((point, index) => (
        <group key={point.incident.incident_id}>
          <primitive
            object={promotionLines[index]}
          />
          <mesh position={point.candidate} scale={.045} name={`candidate:${point.incident.candidate_id}`}>
            <octahedronGeometry args={[1, 0]} />
            <meshBasicMaterial color="#8D7899" transparent opacity={.28} depthWrite={false} />
          </mesh>
          <group
            position={point.durable}
            onPointerDown={(event: ThreeEvent<PointerEvent>) => {
              event.stopPropagation()
              onOpen(point.incident.incident_id)
            }}
          >
            <mesh scale={point.scale} name={`incident:${point.incident.incident_id}`}>
              <dodecahedronGeometry args={[1, 0]} />
              <meshStandardMaterial
                color={point.color}
                emissive={point.color}
                emissiveIntensity={.12}
                roughness={.46}
                metalness={.22}
                transparent
                opacity={.82}
              />
            </mesh>
            <mesh rotation={[Math.PI / 2, 0, 0]} scale={1 + Math.min(.42, point.incident.current_revision * .035)}>
              <torusGeometry args={[.15, .008, 6, 48]} />
              <meshBasicMaterial color={point.color} transparent opacity={.28} depthWrite={false} />
            </mesh>
            {Array.from({ length: Math.min(5, point.incident.source_diversity_count) }, (_, satellite) => {
              const angle = satellite / Math.max(1, Math.min(5, point.incident.source_diversity_count)) * Math.PI * 2
              return (
                <mesh key={satellite} position={[Math.cos(angle) * .24, Math.sin(angle) * .24, 0]} scale={.024}>
                  <sphereGeometry args={[1, 7, 7]} />
                  <meshBasicMaterial color={point.color} transparent opacity={.34} depthWrite={false} />
                </mesh>
              )
            })}
          </group>
        </group>
      ))}
    </group>
  )
}
