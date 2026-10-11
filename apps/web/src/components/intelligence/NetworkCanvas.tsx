import { useEffect, useRef } from 'react'
import cytoscape, { type Core, type ElementDefinition, type LayoutOptions } from 'cytoscape'
import fcose from 'cytoscape-fcose'
import { networkGroup } from './networkPresentation'
import type { NetworkNode, NetworkEdge } from '../../lib/api/network'

cytoscape.use(fcose)
export type NetworkSelection = { kind: 'node' | 'edge'; id: string } | null

export function NetworkCanvas({ nodes, edges, centerId, revision, category, selected, onSelect, resetKey }: {
  nodes: NetworkNode[]; edges: NetworkEdge[]; centerId: string; revision: number
  category: string; selected: NetworkSelection; onSelect: (value: NetworkSelection) => void; resetKey: number
}) {
  const container = useRef<HTMLDivElement>(null)
  const instance = useRef<Core | null>(null)
  const selectRef = useRef(onSelect)
  useEffect(() => { selectRef.current = onSelect }, [onSelect])
  useEffect(() => {
    if (!container.current) return
    const cy = cytoscape({
      container: container.current, minZoom: .18, maxZoom: 2.5,
      style: [
        { selector: 'node', style: {
          width: 22, height: 22, 'background-color': 'data(color)', 'border-width': 5,
          'border-color': '#ffffff', label: 'data(label)', color: '#344054', 'font-size': 12,
          'font-family': 'Inter, system-ui, sans-serif', 'text-valign': 'bottom', 'text-margin-y': 9,
          'text-wrap': 'ellipsis', 'text-max-width': '125px', 'text-background-color': '#fbfcff',
          'text-background-opacity': .9, 'text-background-padding': '3px', 'overlay-opacity': 0,
        } },
        { selector: 'node.core', style: { width: 46, height: 46, 'border-width': 8, 'border-color': '#e0e7ff', 'background-color': '#4263eb', 'font-weight': 600, 'font-size': 14, 'text-max-width': '185px', color: '#1e293b' } },
        { selector: 'edge', style: { width: 1.25, 'line-color': '#c8d2e0', 'curve-style': 'bezier', 'target-arrow-shape': 'triangle', 'target-arrow-color': '#c8d2e0', 'arrow-scale': .65, 'overlay-opacity': 0 } },
        { selector: '.dim', style: { opacity: .12, 'text-opacity': .2 } },
        { selector: '.focus', style: { 'border-color': '#bdccff', 'line-color': '#4263eb', 'target-arrow-color': '#4263eb', 'z-index': 10 } },
        { selector: 'edge.focus', style: { width: 2.5 } },
        { selector: '.new', style: { 'line-color': '#138e83', 'target-arrow-color': '#138e83', 'border-color': '#b5e9dc' } },
        { selector: '.hidden', style: { display: 'none' } },
      ],
    })
    instance.current = cy
    // Keep labels and hit targets legible when fitting a neighborhood on a phone.
    const readableScale = () => {
      const scale = Math.max(.5, .8 / cy.zoom())
      cy.nodes().style({
        'font-size': 12 * scale, width: 18 * scale, height: 18 * scale,
        'text-max-width': `${88 * scale}px`, 'text-margin-y': 7 * scale,
        'border-width': 3 * scale,
      })
      cy.nodes('.core').style({
        width: 34 * scale, height: 34 * scale, 'font-size': 13 * scale,
        'text-max-width': `${110 * scale}px`, 'border-width': 6 * scale,
      })
    }
    cy.on('zoom', readableScale)
    cy.on('tap', 'node', event => selectRef.current({ kind: 'node', id: event.target.id() }))
    cy.on('tap', 'edge', event => selectRef.current({ kind: 'edge', id: event.target.id() }))
    cy.on('tap', event => { if (event.target === cy) selectRef.current(null) })
    cy.on('mouseover', 'node, edge', event => {
      if (cy.elements('.focus').length) return
      const related = event.target.isNode() ? event.target.closedNeighborhood() : event.target.connectedNodes().union(event.target)
      cy.elements().difference(related).addClass('dim')
    })
    cy.on('mouseout', 'node, edge', () => { if (!cy.elements('.focus').length) cy.elements().removeClass('dim') })
    let previousWidth = container.current.clientWidth
    const observer = new ResizeObserver(() => {
      cy.resize()
      const width = container.current?.clientWidth ?? previousWidth
      if (Math.abs(width - previousWidth) > 20 && cy.nodes().length) cy.fit(cy.elements(':visible'), 45)
      previousWidth = width
    })
    observer.observe(container.current)
    return () => { observer.disconnect(); cy.destroy(); instance.current = null }
  }, [])
  useEffect(() => {
    const cy = instance.current
    if (!cy) return
    const prior = cy.nodes().map(node => ({ nodeId: node.id(), position: { ...node.position() } }))
    const definitions: ElementDefinition[] = [
      ...nodes.map(node => ({ data: { id: node.object_id, label: node.label, color: networkGroup(node.object_type).color }, classes: node.object_id === centerId ? 'core' : '' })),
      ...edges.map(edge => ({ data: { id: edge.relation_id, source: edge.source_id, target: edge.target_id } })),
    ]
    const ids = new Set(definitions.map(item => String(item.data.id)))
    cy.batch(() => {
      cy.elements().filter(el => !ids.has(el.id())).remove()
      for (const item of definitions) {
        const existing = cy.getElementById(String(item.data.id))
        if (existing.empty()) cy.add(item)
        else existing.data(item.data)
      }
    })
    if (!nodes.length) return
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    cy.layout({ name: 'fcose', quality: 'default', randomize: true, animate: !reduced,
      animationDuration: 450, fit: !prior.length, padding: 36, nodeRepulsion: 8000,
      idealEdgeLength: 105, nodeSeparation: 70, nodeDimensionsIncludeLabels: true,
      fixedNodeConstraint: prior.length ? prior : [{ nodeId: centerId, position: { x: 0, y: 0 } }],
    } as LayoutOptions).run()
  }, [nodes, edges, centerId])
  useEffect(() => {
    const cy = instance.current
    if (!cy) return
    const visible = new Set(nodes.filter(node => node.created_revision <= revision &&
      (category === 'all' || node.object_id === centerId || networkGroup(node.object_type).id === category)).map(node => node.object_id))
    cy.batch(() => {
      cy.elements().removeClass('hidden dim focus new')
      cy.nodes().forEach(node => { if (!visible.has(node.id())) node.addClass('hidden') })
      for (const edge of edges) {
        const element = cy.getElementById(edge.relation_id)
        if (edge.created_revision > revision || (edge.superseded_revision != null && edge.superseded_revision <= revision) || !visible.has(edge.source_id) || !visible.has(edge.target_id)) element.addClass('hidden')
        else if (edge.created_revision === revision) element.addClass('new')
      }
      if (selected) {
        const el = cy.getElementById(selected.id)
        const related = selected.kind === 'node' ? el.closedNeighborhood() : el.connectedNodes().union(el)
        related.addClass('focus')
        cy.elements().difference(related).addClass('dim')
      }
    })
    const timer = window.setTimeout(() => cy.elements().removeClass('new'), 1400)
    return () => window.clearTimeout(timer)
  }, [nodes, edges, revision, category, centerId, selected])
  useEffect(() => { if (resetKey) instance.current?.fit(instance.current.elements(':visible'), 45) }, [resetKey])
  return <div ref={container} className="knowledge-network-canvas" role="img" aria-label="关系蛛网：点选节点或连线查看详情。下方提供可操作的关系列表。" />
}
