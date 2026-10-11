import { Pulse as Activity } from "@phosphor-icons/react/dist/csr/Pulse"
import { BookOpen } from "@phosphor-icons/react/dist/csr/BookOpen"
import { Stack as Boxes } from "@phosphor-icons/react/dist/csr/Stack"
import { BracketsCurly as Braces } from "@phosphor-icons/react/dist/csr/BracketsCurly"
import { Buildings as Building2 } from "@phosphor-icons/react/dist/csr/Buildings"
import { Compass } from "@phosphor-icons/react/dist/csr/Compass"
import { Flask as FlaskConical } from "@phosphor-icons/react/dist/csr/Flask"
import { GlobeHemisphereWest as Globe2 } from "@phosphor-icons/react/dist/csr/GlobeHemisphereWest"
import { Newspaper as Layers3 } from "@phosphor-icons/react/dist/csr/Newspaper"
import { ChatCircle as MessageCircle } from "@phosphor-icons/react/dist/csr/ChatCircle"
import { Graph as Network } from "@phosphor-icons/react/dist/csr/Graph"
import { Broadcast as Radar } from "@phosphor-icons/react/dist/csr/Broadcast"
import { Scan as ScanLine } from "@phosphor-icons/react/dist/csr/Scan"
import { ShieldCheck } from "@phosphor-icons/react/dist/csr/ShieldCheck"
import { ShieldWarning as ShieldAlert } from "@phosphor-icons/react/dist/csr/ShieldWarning"
import { Sparkle as Sparkles } from "@phosphor-icons/react/dist/csr/Sparkle"
import { Binoculars as Telescope } from "@phosphor-icons/react/dist/csr/Binoculars"
import { type Icon } from "@phosphor-icons/react"

const icons: Record<string, Icon> = {
  world: Globe2, intelligence: Layers3, investigations: Telescope, agents: Network,
  observatory: Activity, start: MessageCircle, direct: MessageCircle, retrieve: BookOpen,
  investigate: Telescope, watch: Radar, monitor: Radar, lookup: BookOpen,
  verify: ShieldCheck, trace: Network, deep: Telescope, wide: Globe2, full: Globe2,
  academic: FlaskConical, researchwork: FlaskConical, document: BookOpen,
  normative: ShieldCheck, normativedocument: ShieldCheck, requirement: ShieldCheck, control: ShieldCheck,
  development: Braces, repository: Braces, repo: Braces, issue: Braces, pullrequest: Braces, commit: Braces, release: Braces,
  incidents: ShieldAlert, incident: ShieldAlert, assets: ScanLine, internetasset: ScanLine, asset: ScanLine,
  vendor: Building2, product: Building2, package: Boxes, softwareversion: Boxes,
  vulnerability: ShieldAlert, independent: Radar, community: Compass, alchemist: Sparkles,
}

/** Standard functional icons; visual identity is reserved for the brand. */
export function ProductGlyph({ kind, size = 24, className = '' }: { kind: string; size?: number; className?: string }) {
  const Icon = icons[kind.toLowerCase()] ?? Layers3
  return <Icon className={`product-glyph ${className}`} size={size} weight="regular" aria-hidden="true" />
}

export function BrandMark({ size = 32 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 40 40" fill="none" aria-hidden="true">
    <path d="M20 9H13a7 7 0 0 0 0 14h2a4 4 0 0 1 0 8H6M23 31V9h12M23 20h10" stroke="currentColor" strokeWidth="4" strokeLinecap="square" />
  </svg>
}
