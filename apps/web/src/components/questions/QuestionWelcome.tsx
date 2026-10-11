import { useQuery } from '@tanstack/react-query'
import { ArrowUpRight, BookOpen, Compass, ShieldCheck } from 'lucide-react'
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
  const recommended = recommendations.data?.items.find(item => item.object_id !== followed?.object_id && isSecurityQuestion(item.object_type, item.label))
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
    <div className="qa-welcome-identity"><BrandMark size={34}/><span>SecFusion<span className="qa-assistant-description">{text('情报问答', 'Intelligence assistant')}</span></span></div>
    <div className="qa-welcome-message"><span className="qa-welcome-eyebrow">ASK / EVIDENCE</span><h2>{text('从一个问题，走向可核对的答案。', 'Ask a question. Follow the evidence.')}</h2><p>{text('像平常聊天一样提问。需要时，我会检索材料、追踪事件，并把依据与你分享。', 'Ask naturally. I can search the material, follow a story, and show you the evidence behind an answer.')}</p></div>
    <div className="qa-suggestions-heading"><span>{personalized ? text('从你的关注开始', 'Start with your interests') : text('从这里开始', 'Start here')}</span>{authenticated && <Link to="/workspace/profile">{text('调整兴趣', 'Your interests')}<ArrowUpRight size={14}/></Link>}</div>
    <div className={`qa-welcome-actions ${article ? 'has-article' : ''}`}>
      <div className="qa-welcome-prompt-list">
        <button className="qa-starter-question" onClick={() => onSelect(first.prompt)}><span className="qa-prompt-icon"><Compass size={20}/></span><span className="qa-prompt-copy"><small>{first.label}</small><strong>{first.title}</strong></span><ArrowUpRight size={18}/></button>
        {alternatives.map(({ title, prompt, label, icon: Icon }) => <button className="qa-prompt-option" key={title} onClick={() => onSelect(prompt)}><span className="qa-prompt-icon"><Icon size={18}/></span><span className="qa-prompt-copy"><small>{label}</small><strong>{title}</strong></span><ArrowUpRight size={16}/></button>)}
      </div>
      {article && <button className="qa-recommended-article" onClick={() => onSelect(article.prompt)}><span className="qa-recommended-kicker"><BookOpen size={16}/>{text('正在读的情报', 'From the intelligence feed')}</span><strong>{article.title}</strong><span className="qa-recommended-source"><SourceIdentity source={recommended?.evidence[0]?.source_id} url={recommended?.evidence[0]?.canonical_url}/></span><span className="qa-recommended-action">{text('围绕这条材料提问', 'Ask about this story')}<ArrowUpRight size={15}/></span></button>}
    </div>
  </div>
}

function isSecurityQuestion(type: string, title: string) {
  return type === 'Vulnerability' || type === 'Incident' || /CVE-|安全|漏洞|攻击|入侵|威胁|风险|防护|恶意|钓鱼|security|cyber|vulnerab|attack|intrusion|threat|exploit|malware|breach|phishing|incident/i.test(title)
}
