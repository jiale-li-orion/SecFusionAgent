import { useNavigate } from 'react-router-dom'
import type { IncidentDetail } from '../../lib/api'
import { KnowledgeNetwork } from './KnowledgeNetwork'

/** Incident and canonical dossiers share one explorable graph; revision domains remain separate. */
export function IncidentEvolution({ incident, onEvidence }: { incident: IncidentDetail; onEvidence: (ref: string) => void }) {
  const navigate = useNavigate()
  return <KnowledgeNetwork incident objectId={incident.incident.incident_id} onEvidence={onEvidence}
    onOpenTarget={objectId => navigate(`/intelligence?${new URLSearchParams({ object: objectId, view: 'graph' })}`)} />
}
