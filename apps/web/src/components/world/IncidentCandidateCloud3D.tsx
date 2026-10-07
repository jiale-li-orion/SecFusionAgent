import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

import type { WorldIncidentCandidate } from '../../lib/api'

function stablePhase(value: string) {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0) / 0xffffffff * Math.PI * 2
}

export function IncidentCandidateCloud3D({ candidates, reduceMotion }: { candidates: WorldIncidentCandidate[]; reduceMotion: boolean }) {
  const group = useRef<THREE.Group>(null)
  const points = useMemo(() => candidates.slice(0, 24).map((candidate, index) => {
    const angle = stablePhase(candidate.candidate_id)
    const radius = 1.16 + (index % 4) * .13
    return {
      candidate,
      position: new THREE.Vector3(
        Math.cos(angle) * radius,
        Math.sin(angle) * radius,
        -.05 + (index % 5) * .055,
      ),
    }
  }), [candidates])

  useFrame((state) => {
    if (!group.current || reduceMotion) return
    group.current.rotation.z = state.clock.elapsedTime * .018
  })

  if (points.length === 0) return null
  return (
    <group ref={group} position={[1.6, -2.05, -.35]}>
      {points.map(({ candidate, position }) => (
        <mesh
          key={candidate.candidate_id}
          position={position}
          scale={.034 + Math.min(.022, candidate.watch_priority / 5000)}
          name={`incident-candidate:${candidate.candidate_id}`}
        >
          <octahedronGeometry args={[1, 0]} />
          <meshBasicMaterial
            color={candidate.pinned ? '#B9824C' : '#8D7899'}
            transparent
            opacity={candidate.anchor_count > 0 ? .58 : .28}
            depthWrite={false}
          />
        </mesh>
      ))}
    </group>
  )
}
