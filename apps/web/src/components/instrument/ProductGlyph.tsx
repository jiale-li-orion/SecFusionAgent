import { Activity, BookOpen, Boxes, Braces, Building2, Compass, FlaskConical, Globe2, Layers3, MessageCircle, Network, Radar, ScanLine, ShieldCheck, ShieldAlert, Sparkles, Telescope, type LucideIcon } from 'lucide-react'

const icons: Record<string, LucideIcon> = {
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
  return <Icon className={`product-glyph ${className}`} size={size} strokeWidth={1.7} aria-hidden="true" />
}

export function BrandMark({ size = 32 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
    <rect width="32" height="32" rx="10" fill="#4263eb" />
    <path d="m8 12 8-4 8 4-8 4-8-4Z" fill="white" />
    <path d="m8 17 8 4 8-4M8 22l8 4 8-4" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
}
