import { useQuery } from '@tanstack/react-query'
import { ArrowUpRight } from '../ui/icons'
import { ActionIndicator } from '../ui/action-indicator'
import { Item, ItemContent, ItemTitle, ItemDescription, ItemActions } from '../ui/item'
import { Button } from '../ui/button'
import { readableObjectTitle } from '../../lib/source-identity'
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
  const recommended = recommendations.data?.items.find(item => item.object_id !== followed?.object_id && isSecurityQuestion(item.object_type, item.label))
  const personalized = Boolean(followed || keyword || recommended?.reasons.length)
  const prompts = [
    followed ? {
      title: followed.label,
      prompt: text(`我关注的 ${followed.label} 最近有哪些安全动态？请说明证据来源。`, `What are the latest security developments for ${followed.label}? Include the evidence sources.`),
      label: text('来自你的关注', 'From your follows'),
    } : keyword ? {
      title: text(`${keyword} 有哪些新动态？`, `What is new in ${keyword}?`),
      prompt: text(`最近有哪些与 ${keyword} 相关的安全动态值得关注？`, `Which recent security developments related to ${keyword} deserve attention?`),
      label: text('来自你的关注领域', 'From your interests'),
    } : {
      title: text('最近有哪些安全事件值得关注？', 'Which security stories matter right now?'),
      prompt: text('最近有哪些安全事件值得关注？请整理事件经过和可靠来源。', 'Which recent security incidents deserve attention? Summarize what happened and the reliable sources.'),
      label: text('发现新动态', 'Discover'),
    },
    recommended ? {
      title: readableObjectTitle(recommended.label, recommended.evidence[0]?.canonical_url, recommended.evidence[0]?.source_id),
      prompt: text(`帮我了解 ${recommended.label}，有哪些已确认的事实和还未解决的问题？`, `Help me understand ${recommended.label}. What is confirmed, and what remains unresolved?`),
      label: recommended.reasons.length ? text('与你的兴趣相关', 'Related to your interests') : text('从情报中探索', 'Explore intelligence'),
    } : {
      title: text('一次供应链攻击，是怎样发生的？', 'How does a supply-chain attack unfold?'),
      prompt: text('最近有哪些典型的软件供应链攻击？请结合证据解释攻击路径和防护建议。', 'Explain recent software supply-chain attacks, their attack paths, and evidence-based defenses.'),
      label: text('深入理解', 'Understand'),
    },
    {
      title: text('修复一个漏洞，还需要核对什么？', 'What should I check beyond a patch?'),
      prompt: text('评估一个漏洞是否已经修复时，应该核对哪些版本、补丁和证据？', 'When assessing whether a vulnerability is fixed, which versions, patches, and evidence should I verify?'),
      label: text('核验证据', 'Verify'),
    },
  ]
  return <div className="qa-conversation-welcome">
    <div className="qa-welcome-intro">
    <span className="qa-welcome-kicker">{text('从好奇出发，以证据抵达。', 'Follow your curiosity. Find the evidence.')}</span>
    <img className="qa-welcome-sculpture" src={`${import.meta.env.BASE_URL}art/night-reading.webp`} width="220" height="220" alt="" aria-hidden="true" draggable={false}/>
    <h2>{text('今天想了解什么？', 'What would you like to understand?')}</h2>
    <p>{text('聊聊你关心的安全问题。我会帮你查资料、梳理来龙去脉，并保留每一个结论的来源。', 'Ask about a security question. I can find sources, connect the story, and keep the evidence behind each conclusion.')}</p>
    </div>
    <div className="qa-welcome-starters"><div className="qa-starters-heading flex items-center justify-between gap-3 text-xs text-muted-foreground"><span>{personalized ? text('从你的关注开始', 'From your interests') : text('试着问我', 'Try asking')}</span>{authenticated && <Button variant="ghost" size="sm" asChild><Link to="/workspace/profile">{text('调整兴趣', 'Your interests')}<ArrowUpRight size={14}/></Link></Button>}</div>
    <div className="qa-starter-list">{prompts.map(({ title, prompt, label }) => <Item asChild key={title} className="qa-starter-item w-full border-0"><button onClick={() => onSelect(prompt)} className="text-left"><ItemContent className="qa-starter-copy"><ItemTitle className="font-normal">{title}</ItemTitle><ItemDescription className="text-xs">{label}</ItemDescription></ItemContent><ItemActions><ActionIndicator /></ItemActions></button></Item>)}</div></div>
  </div>
}

function isSecurityQuestion(type: string, title: string) {
  return type === 'Vulnerability' || type === 'Incident' || /CVE-|安全|漏洞|攻击|入侵|威胁|风险|防护|恶意|钓鱼|security|cyber|vulnerab|attack|intrusion|threat|exploit|malware|breach|phishing|incident/i.test(title)
}
