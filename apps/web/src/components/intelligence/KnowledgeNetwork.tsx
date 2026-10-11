import { lazy, Suspense, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import * as Dialog from '@radix-ui/react-dialog'
import { ArrowsOut } from "@phosphor-icons/react/dist/csr/ArrowsOut"
import { Crosshair } from "@phosphor-icons/react/dist/csr/Crosshair"
import { SlidersHorizontal } from "@phosphor-icons/react/dist/csr/SlidersHorizontal"
import { X } from "@phosphor-icons/react/dist/csr/X"
import { ArrowUpRight } from "@phosphor-icons/react/dist/csr/ArrowUpRight"
import { Plus } from "@phosphor-icons/react/dist/csr/Plus"
import { CircleNotch } from "@phosphor-icons/react/dist/csr/CircleNotch"
import { getKnowledgeNetwork, type KnowledgeNetwork as NetworkData } from '../../lib/api/network'
import { evidenceFieldLabel, formatValue } from '../../lib/intelligencePresentation'
import { useI18n } from '../../lib/i18n'
import { Button } from '../ui/button'
import { Sheet, SheetContent, SheetTitle, SheetDescription, SheetHeader } from '../ui/sheet'
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuRadioGroup, DropdownMenuRadioItem } from '../ui/dropdown-menu'
import { EvidenceCapsules } from './KnowledgeSurfaces'
import type { NetworkSelection } from './NetworkCanvas'
import { networkDate, networkGroup, networkGroups } from './networkPresentation'
import './knowledge-network.css'

const NetworkCanvas = lazy(() => import('./NetworkCanvas').then(module => ({ default: module.NetworkCanvas })))

export function KnowledgeNetwork({ objectId, onEvidence, onOpenTarget, incident = false }: {
  objectId: string; incident?: boolean; onEvidence: (ref: string) => void; onOpenTarget: (id: string) => void
}) {
  return <KnowledgeNetworkExplorer key={objectId} incident={incident} objectId={objectId} onEvidence={onEvidence} onOpenTarget={onOpenTarget} />
}

function KnowledgeNetworkExplorer({ objectId, onEvidence, onOpenTarget, incident = false }: {
  objectId: string; incident?: boolean; onEvidence: (ref: string) => void; onOpenTarget: (id: string) => void
}) {
  const { text } = useI18n()
  const query = useQuery({ queryKey: ['knowledge-network', objectId, incident], queryFn: ({ signal }) => getKnowledgeNetwork(objectId, { limit: window.matchMedia('(max-width: 700px)').matches ? 16 : 40 }, signal, incident), staleTime: Infinity })
  const [pages, setPages] = useState<Array<{ focus: string; data: NetworkData }>>([])
  const [selection, setSelection] = useState<NetworkSelection>(null)
  const [category, setCategory] = useState('all')
  const [full, setFull] = useState(false)
  const [resetKey, setResetKey] = useState(0)
  const [revision, setRevision] = useState<number | null>(null)
  const [loadingFocus, setLoadingFocus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const data = useMemo(() => {
    if (!query.data) return null
    const records = [query.data, ...pages.filter(page => page.data.snapshot_revision === query.data.snapshot_revision).map(page => page.data)]
    return {
      ...query.data,
      nodes: [...new Map(records.flatMap(record => record.nodes).map(node => [node.object_id, node])).values()],
      edges: [...new Map(records.flatMap(record => record.edges).map(edge => [edge.relation_id, edge])).values()],
    }
  }, [query.data, pages])
  const now = revision ?? data?.snapshot_revision ?? 0
  const revisions = useMemo(() => data ? [...new Set([
    ...data.nodes.map(node => node.created_revision),
    ...data.edges.flatMap(edge => [edge.created_revision, ...(edge.superseded_revision == null ? [] : [edge.superseded_revision])]),
    data.snapshot_revision,
  ])].filter(value => value <= data.snapshot_revision).sort((a, b) => a - b) : [], [data])
  const dates = new Map(data?.edges.flatMap(edge => [
    [edge.created_revision, edge.created_at] as const,
    ...(edge.superseded_revision == null ? [] : [[edge.superseded_revision, edge.superseded_at] as const]),
  ]) ?? [])
  const selectedNode = selection?.kind === 'node' ? data?.nodes.find(node => node.object_id === selection.id) : undefined
  const selectedEdge = selection?.kind === 'edge' ? data?.edges.find(edge => edge.relation_id === selection.id) : undefined
  const focus = selectedNode?.object_id ?? objectId
  const focusPage = [...pages].reverse().find(page => page.focus === focus && page.data.snapshot_revision === data?.snapshot_revision)?.data ?? (focus === objectId ? query.data : undefined)
  const activeEdges = data?.edges.filter(edge => edge.created_revision <= now && (edge.superseded_revision == null || edge.superseded_revision > now)) ?? []
  const labels = new Map(data?.nodes.map(node => [node.object_id, node.label]))
  const visibleIds = new Set(data?.nodes.filter(node => node.created_revision <= now && (category === 'all' || node.object_id === objectId || networkGroup(node.object_type).id === category)).map(node => node.object_id))
  const visibleEdges = activeEdges.filter(edge => visibleIds.has(edge.source_id) && visibleIds.has(edge.target_id))
  const nodeEdges = activeEdges.filter(edge => edge.source_id === selectedNode?.object_id || edge.target_id === selectedNode?.object_id)
  async function expand() {
    if (!data || loadingFocus || data.nodes.length >= 200) return
    setLoadingFocus(focus)
    setError(null)
    try {
      const page = await getKnowledgeNetwork(objectId, { focusId: focus, existingIds: data.nodes.map(node => node.object_id), cursor: focusPage?.next_cursor ?? undefined, revision: data.snapshot_revision }, undefined, incident)
      setPages(current => [...current, { focus, data: page }])
    } catch (cause) { setError(cause instanceof Error ? cause.message : '关联展开失败，请重试') }
    finally { setLoadingFocus(null) }
  }
  function chooseRevision(next: number) { setRevision(next); setSelection(null) }
  const selectedEvidence = selectedEdge?.evidence ?? [...new Map(nodeEdges.flatMap(edge => edge.evidence).map(ref => [ref.observation_id, ref])).values()]
  const detail = <>
    <SheetHeader>
      <SheetTitle>{selectedNode?.label ?? (selectedEdge ? evidenceFieldLabel(selectedEdge.relation_type, text) : '')}</SheetTitle>
      <SheetDescription>{selectedNode ? networkGroup(selectedNode.object_type).label : text('这条关联的记录与依据', 'Recorded connection and supporting evidence')}</SheetDescription>
    </SheetHeader>
    <div className="network-detail-body">
      {selectedEdge && <>
        <div className="network-relationship-sentence"><strong>{labels.get(selectedEdge.source_id)}</strong><span>{evidenceFieldLabel(selectedEdge.relation_type, text)} →</span><strong>{labels.get(selectedEdge.target_id)}</strong></div>
        <p className="network-detail-meta">{text('系统建立于', 'Recorded')} {networkDate(selectedEdge.created_at)}</p>
        {Object.entries(selectedEdge.qualifier).length > 0 && <dl className="network-qualifiers">{Object.entries(selectedEdge.qualifier).map(([key, value]) => <div key={key}><dt>{evidenceFieldLabel(key, text)}</dt><dd>{formatValue(value)}</dd></div>)}</dl>}
      </>}
      {selectedNode && <>
        <p>{text(`当前网络中有 ${nodeEdges.length} 条关联。`, `${nodeEdges.length} connections in this network.`)}</p>
        <div className="network-detail-actions">
          <Button disabled={!!loadingFocus || data!.nodes.length >= 200 || (focusPage != null && !focusPage.next_cursor)} onClick={() => void expand()}>{loadingFocus ? <CircleNotch className="animate-spin" /> : <Plus />}{text('展开关联', 'Expand connections')}</Button>
          {(!incident || selectedNode.canonical_object_id) && <Button variant="outline" onClick={() => { setSelection(null); setFull(false); onOpenTarget(selectedNode.canonical_object_id ?? selectedNode.object_id) }}>{text('打开档案', 'Open dossier')}<ArrowUpRight /></Button>}
        </div>
        {error && <p role="alert" className="network-error">{error}</p>}
        {focusPage && <p className="network-detail-meta">{focusPage.remaining_count ? text(`还有 ${focusPage.remaining_count} 个关联对象未展开`, `${focusPage.remaining_count} connected objects remaining`) : text('本次读取范围内没有更多邻居', 'No more neighbors in this reading scope')}</p>}
      </>}
      {selectedNode?.event_time && <p className="network-detail-meta">来源事件时间 · {networkDate(selectedNode.event_time)}</p>}
      {selectedNode?.evidence_ref && <Button variant="outline" onClick={() => { setSelection(null); setFull(false); onEvidence(selectedNode.evidence_ref!) }}>打开来源证据<ArrowUpRight /></Button>}
      <h3>{text('关联证据', 'Supporting evidence')}</h3>
      <EvidenceCapsules evidence={selectedEvidence} onEvidence={ref => { setSelection(null); setFull(false); onEvidence(ref) }} />
      <details className="network-record"><summary>{text('原始记录', 'Record details')}</summary><code>{selectedNode?.object_id ?? selectedEdge?.relation_id}</code><p>{selectedNode?.object_type ?? selectedEdge?.origin}</p></details>
    </div>
  </>
  const surface = <div className="knowledge-network-surface">
    <header className="knowledge-network-toolbar">
      <div><strong>{text('关联网络', 'Connections')}</strong><span>{text(`${data?.nodes.filter(node => node.created_revision <= now).length ?? 0} 个对象 · ${activeEdges.length} 条关联`, `${data?.nodes.filter(node => node.created_revision <= now).length ?? 0} objects · ${activeEdges.length} connections`)}</span></div>
      <div className="network-tools">
        <DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" size="sm"><SlidersHorizontal size={18} />{text('筛选', 'Filter')}{category !== 'all' && <i className="network-filter-dot" />}</Button></DropdownMenuTrigger>
          <DropdownMenuContent className="network-filter-menu" align="end"><DropdownMenuRadioGroup value={category} onValueChange={value => { setCategory(value); setSelection(null) }}><DropdownMenuRadioItem value="all">{text('全部关联', 'All connections')}</DropdownMenuRadioItem>{networkGroups.map(group => <DropdownMenuRadioItem key={group.id} value={group.id}>{group.label}</DropdownMenuRadioItem>)}</DropdownMenuRadioGroup></DropdownMenuContent>
        </DropdownMenu>
        <Button variant="ghost" size="icon" title="回到中心" aria-label="回到中心" onClick={() => { setSelection(null); setResetKey(value => value + 1) }}><Crosshair size={20} /></Button>
        <Button variant="ghost" size="icon" title={full ? '退出全屏' : '全屏探索'} aria-label={full ? '退出全屏' : '全屏探索'} onClick={() => setFull(value => !value)}>{full ? <X size={20} /> : <ArrowsOut size={20} />}</Button>
      </div>
    </header>
    {error && <p role="alert" className="network-error">{error}</p>}
    <div className="knowledge-network-stage">
      {query.isPending ? <div className="network-state"><CircleNotch className="animate-spin" size={26} /><p>{text('正在连接知识与证据…', 'Connecting knowledge and evidence…')}</p></div> : query.isError ? <div className="network-state" role="alert"><p>{query.error.message}</p><Button variant="outline" onClick={() => void query.refetch()}>{text('重新读取', 'Retry')}</Button></div> : data && <>
        <Suspense fallback={<div className="network-state" role="status">正在绘制关系网络…</div>}><NetworkCanvas nodes={data.nodes} edges={data.edges} centerId={data.center_id} revision={now} category={category} selected={selection} onSelect={setSelection} resetKey={resetKey} /></Suspense>
        <div className="network-legend">{networkGroups.filter(group => data.nodes.some(node => networkGroup(node.object_type).id === group.id)).map(group => <span key={group.id}><i style={{ background: group.color }} />{group.label}</span>)}</div>
        <span className="network-gesture-hint">{text('点选查看 · 拖动探索 · 缩放', 'Select · Pan · Zoom')}</span>
        {!data.edges.length && <p className="network-no-relations">{text('这个对象尚无已记录的关联', 'No recorded connections yet')}</p>}
      </>}
    </div>
    {data && <footer className="network-history">
      <div><strong>{text('富化历程', 'Knowledge growth')}</strong><span>{revision == null || now === data.snapshot_revision ? text('当前记录', 'Current record') : networkDate(dates.get(now) ?? data.nodes.find(node => node.created_revision === now)?.created_at ?? null)}</span></div>
      <input type="range" aria-label="回看系统建立关系的过程" min={0} max={Math.max(0, revisions.length - 1)} value={Math.max(0, revisions.indexOf(now))} disabled={revisions.length < 2} onChange={event => chooseRevision(revisions[Number(event.target.value)])} />
      <p>{text('按系统提交时间回看已加载关系；来源事件时间见证据详情。名称与证据显示当前留存版本。', 'Replay loaded relationships by commit time. Source event times are in evidence details; labels and evidence show the retained version.')}</p>
      <div className="network-history-actions"><Button size="sm" variant="ghost" disabled={query.isFetching || !!loadingFocus} onClick={() => { setPages([]); setRevision(null); setSelection(null); setError(null); void query.refetch() }}>{text('读取最新关系', 'Read latest connections')}</Button><details><summary>{text('读取范围', 'Reading scope')}</summary><p>{incident ? text('事件视图最多读取 200 条事件记录与 200 条来源记录。回放限于已加载关联，并非完整历史。', 'The incident view reads up to 200 event and 200 source records. Playback covers loaded associations, not complete history.') : text('每次从一个节点展开邻居，画布最多加载 200 个对象。历史名称与证据没有完整版本快照。', 'Expand one neighborhood at a time, up to 200 objects. Historical labels and evidence are not fully versioned.')}</p></details></div>
    </footer>}
    {data && <div className="network-reading-footer">
      <span>{query.data?.remaining_count ? text(`中心对象还有 ${[...pages].reverse().find(page => page.focus === objectId && page.data.snapshot_revision === data.snapshot_revision)?.data.remaining_count ?? query.data.remaining_count} 个关联对象可展开`, 'More connections are available from the center object') : text('当前显示已加载对象的局部关联网络', 'Showing the loaded local network')}</span>
      <details className="network-accessible-list"><summary>{text('用列表探索对象与关系', 'Explore objects and connections as a list')}</summary><div className="network-node-list">{data.nodes.filter(node => visibleIds.has(node.object_id)).map(node => <Button key={node.object_id} size="sm" variant="outline" onClick={() => setSelection({ kind: 'node', id: node.object_id })}>{node.label}</Button>)}</div>{visibleEdges.map(edge => <button key={edge.relation_id} onClick={() => setSelection({ kind: 'edge', id: edge.relation_id })}><span>{labels.get(edge.source_id)}</span><small>{evidenceFieldLabel(edge.relation_type, text)} →</small><span>{labels.get(edge.target_id)}</span><ArrowUpRight size={16} /></button>)}</details>
    </div>}
  </div>
  return <section className="knowledge-network">
    {!full && surface}
    <Dialog.Root open={full} onOpenChange={setFull}><Dialog.Portal><Dialog.Overlay className="network-fullscreen-overlay" /><Dialog.Content className="network-fullscreen"><Dialog.Title className="sr-only">关系网络全屏探索</Dialog.Title><Dialog.Description className="sr-only">拖动和缩放关系图，点选节点或连线查看证据。</Dialog.Description>{surface}</Dialog.Content></Dialog.Portal></Dialog.Root>
    <Sheet open={selection != null} onOpenChange={open => { if (!open) setSelection(null) }} modal><SheetContent className="network-detail-sheet">{detail}</SheetContent></Sheet>

  </section>
}
