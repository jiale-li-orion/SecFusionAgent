import { useQuery } from '@tanstack/react-query'
import { ArrowUpRight, BookOpen, Compass, ShieldCheck } from 'lucide-react'
import { Item, ItemContent, ItemDescription, ItemMedia, ItemTitle } from '../ui/item'
import { Button } from '../ui/button'
import { SourceIdentity } from '../ui/source-identity'
import { readableObjectTitle } from '../../lib/source-identity'
import { BrandMark } from '../instrument/ProductGlyph'
import { Link } from 'react-router-dom'
import { getIntelligencePreferences, getIntelligenceRecommendations } from '../../lib/api/recommendations'
import { useAuth } from '../../lib/auth'
import { useI18n } from '../../lib/i18n'

export function QuestionWelcome({ onSelect }: { onSelect: (prompt: string) => void }) {
  const { text } = useI18n()
  const { authenticated } = useAuth()
  const preferences = useQuery({ queryKey: ['intelligence-preferences'], queryFn: getIntelligencePreferences, enabled: authenticated, retry: false, staleTime: 60_000 })
  const recommendations = useQuery({ queryKey: ['intelligence-recommendations', 3], queryFn: () => getIntelligenceRecommendations(3), enabled: authenticated, retry: false, staleTime: 60_000 })
  const followed = preferences.data?.target_objects[0]
  const keyword = preferences.data?.keywords[0]
  const recommended = recommendations.data?.items.find(item => item.object_id !== followed?.object_id)
  const personalized = Boolean(followed || keyword || recommended?.reasons.length)
  const prompts = [
    followed ? {
      title: followed.label,
      prompt: text(`我关注的 ${followed.label} 最近有哪些安全动态？请说明证据来源。`, `What are the latest security developments for ${followed.label}? Include the evidence sources.`),
      label: text('来自你的关注', 'From your follows'), icon: Compass,
    } : keyword ? {
      title: text(`${keyword} 有哪些新动态？`, `What is new in ${keyword}?`),
      prompt: text(`最近有哪些与 ${keyword} 相关的安全动态值得关注？`, `Which recent security developments related to ${keyword} deserve attention?`),
      label: text('来自你的关注领域', 'From your interests'), icon: Compass,
    } : {
      title: text('最近有哪些安全事件值得关注？', 'Which security stories matter right now?'),
      prompt: text('最近有哪些安全事件值得关注？请整理事件经过和可靠来源。', 'Which recent security incidents deserve attention? Summarize what happened and the reliable sources.'),
      label: text('发现新动态', 'Discover'), icon: Compass,
    },
    recommended ? {
      title: readableObjectTitle(recommended.label, recommended.evidence[0]?.canonical_url, recommended.evidence[0]?.source_id),
      prompt: text(`帮我了解 ${recommended.label}，有哪些已确认的事实和还未解决的问题？`, `Help me understand ${recommended.label}. What is confirmed, and what remains unresolved?`),
      label: recommended.reasons.length ? text('与你的兴趣相关', 'Related to your interests') : text('从情报中探索', 'Explore intelligence'), icon: BookOpen,
    } : {
      title: text('一次供应链攻击，是怎样发生的？', 'How does a supply-chain attack unfold?'),
      prompt: text('最近有哪些典型的软件供应链攻击？请结合证据解释攻击路径和防护建议。', 'Explain recent software supply-chain attacks, their attack paths, and evidence-based defenses.'),
      label: text('深入理解', 'Understand'), icon: BookOpen,
    },
    {
      title: text('修复一个漏洞，还需要核对什么？', 'What should I check beyond a patch?'),
      prompt: text('评估一个漏洞是否已经修复时，应该核对哪些版本、补丁和证据？', 'When assessing whether a vulnerability is fixed, which versions, patches, and evidence should I verify?'),
      label: text('核验证据', 'Verify'), icon: ShieldCheck,
    },
  ]
  const first = prompts[0]
  const article = recommended ? prompts[1] : null
  const alternatives = recommended ? [prompts[2]] : prompts.slice(1)
  return <div className="qa-welcome">
    <div className="qa-welcome-identity"><BrandMark size={36}/><span>SecFusion<span className="qa-assistant-description">{text('安全情报助手', 'Intelligence assistant')}</span></span></div>
    <div className="qa-welcome-message"><h2>{text('今天，想了解什么？', 'What’s on your mind?')}</h2><p>{text('追踪安全动态，核对一个结论，或把一个问题查清楚。我们可以从这里开始。', 'Follow a security story, verify a claim, or work through a question. Let’s start here.')}</p></div>
    <div className="qa-suggestions-heading"><span>{personalized ? text('从你的关注开始', 'From your interests') : text('你可以这样问', 'A few places to start')}</span>{authenticated && <Link to="/workspace/profile">{text('调整兴趣', 'Your interests')}<ArrowUpRight size={12}/></Link>}</div>
    <Button variant="outline" className="qa-starter-question" onClick={() => onSelect(first.prompt)}>{first.title}<ArrowUpRight size={17}/></Button>
    {article && <Item variant="outline" asChild className="qa-recommended-article"><button onClick={() => onSelect(article.prompt)}>
      <ItemContent><ItemDescription>{article.label}</ItemDescription><ItemTitle>{article.title}</ItemTitle><SourceIdentity source={recommended?.evidence[0]?.source_id} url={recommended?.evidence[0]?.canonical_url}/></ItemContent>
      <ItemMedia><ArrowUpRight size={20}/></ItemMedia>
    </button></Item>}
    <div className="qa-prompt-chips">{alternatives.map(({ title, prompt, icon: Icon }) => <Button variant="ghost" key={title} onClick={() => onSelect(prompt)}><Icon size={16}/><span>{title}</span><ArrowUpRight size={14}/></Button>)}</div>
  </div>
}
