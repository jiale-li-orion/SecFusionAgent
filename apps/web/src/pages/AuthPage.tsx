import { useEffect, useState, type FormEvent } from 'react'
import { ArrowRight, Eye, EyeOff, LockKeyhole } from 'lucide-react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { HeroArtifact } from '../components/instrument/HeroArtifact'
import { AccountRequestError } from '../lib/api/auth'
import { safeAccountReturnTo, useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'

export function AuthPage() {
  const [params] = useSearchParams()
  const mode = params.get('mode') === 'register' ? 'register' : 'login'
  return <AccountForm key={mode} mode={mode} returnTo={safeAccountReturnTo(params.get('returnTo'))} />
}

function AccountForm({ mode, returnTo }: { mode: 'login' | 'register'; returnTo: string }) {
  const auth = useAuth()
  const { text } = useI18n()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [visible, setVisible] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const registering = mode === 'register'

  useEffect(() => {
    if (auth.authenticated && !auth.loading) navigate(returnTo, { replace: true })
  }, [auth.authenticated, auth.loading, navigate, returnTo])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (auth.loading || auth.isBusy) return
    setError(null)
    if (registering && password !== confirmation) {
      setError('password_mismatch')
      return
    }
    try {
      if (registering) await auth.register({ email: email.trim(), display_name: name.trim(), password })
      else await auth.login({ email: email.trim(), password })
      setPassword('')
      setConfirmation('')
      navigate(returnTo, { replace: true })
    } catch (failure) {
      setError(failure instanceof AccountRequestError ? failure.code : 'network_error')
    }
  }

  const errors: Record<string, [string, string]> = {
    invalid_credentials: ['邮箱或密码不正确，请重新输入。', 'The email or password is incorrect. Please try again.'],
    account_exists: ['该邮箱已注册，可以切换到登录。', 'This email already has an account. Switch to sign in.'],
    csrf_rejected: ['当前请求未通过验证，请刷新页面后重试。', 'The request could not be verified. Refresh the page and try again.'],
    validation_error: ['请检查邮箱、显示名称和密码是否符合要求。', 'Check that your email, display name and password meet the requirements.'],
    password_mismatch: ['两次输入的密码不一致。', 'The passwords do not match.'],
    network_error: ['暂时无法连接账户服务，请重试。', 'The account service could not be reached. Please retry.'],
    request_failed: ['账户操作暂时未完成，请稍后重试。', 'The account request did not finish. Please try again.'],
  }
  const switchUrl = `/auth?${new URLSearchParams({ mode: registering ? 'login' : 'register', returnTo }).toString()}`

  return <main className="auth-page">
    <section className="auth-art">
      <div className="auth-art-model" aria-hidden="true"><HeroArtifact kind="DecisionRole" /></div>
      <small>SecFusion</small><h1>{text('让情报与你的工作相连', 'Connect intelligence to your work')}</h1>
      <p>{text('保存关注范围，继续你的调查，在同一个账户下找回提问与任务。', 'Save your interests, continue investigations, and return to your questions and tasks in one account.')}</p>
    </section>
    <section className="auth-panel">
      <header><small>{registering ? text('创建账户', 'CREATE AN ACCOUNT') : text('欢迎回来', 'WELCOME BACK')}</small>
        <h2>{registering ? text('开始你的情报工作', 'Start your intelligence work') : text('登录 SecFusion', 'Sign in to SecFusion')}</h2></header>
      {auth.loading ? <p className="auth-state" role="status">{text('正在恢复登录状态…', 'Restoring your sign-in…')}</p>
        : auth.error ? <div className="auth-state" role="alert"><p>{text('暂时无法确认登录状态。请重试后继续。', 'Your sign-in could not be checked. Retry to continue.')}</p><button type="button" onClick={() => void auth.refresh()}>{text('重新读取', 'Retry')}</button></div>
          : auth.authenticated ? <p className="auth-state" role="status">{text('已登录，正在返回…', 'Signed in. Returning…')}</p>
            : <form className="auth-form" onSubmit={(event) => void submit(event)}>
              {registering && <label htmlFor="account-display-name">{text('显示名称', 'Display name')}
                <input id="account-display-name" name="display_name" autoComplete="nickname" required maxLength={80} value={name} disabled={auth.isBusy} onChange={(event) => setName(event.target.value)} /></label>}
              <label htmlFor="account-email">{text('邮箱', 'Email')}
                <input id="account-email" name="email" type="email" inputMode="email" autoComplete="username" autoCapitalize="none" spellCheck={false} required maxLength={254} value={email} disabled={auth.isBusy} onChange={(event) => setEmail(event.target.value)} /></label>
              <label htmlFor="account-password">{text('密码', 'Password')}
                <div className="auth-password"><input id="account-password" name="password" type={visible ? 'text' : 'password'} autoComplete={registering ? 'new-password' : 'current-password'} required minLength={registering ? 12 : 1} maxLength={128} value={password} disabled={auth.isBusy} onChange={(event) => setPassword(event.target.value)} />
                  <button type="button" aria-label={visible ? text('隐藏密码', 'Hide password') : text('显示密码', 'Show password')} aria-pressed={visible} onClick={() => setVisible((value) => !value)}>{visible ? <EyeOff size={17} /> : <Eye size={17} />}</button></div>
              </label>
              {registering && <><small>{text('请使用 12–128 个字符的密码。', 'Use a password with 12–128 characters.')}</small>
                <label htmlFor="account-confirm-password">{text('确认密码', 'Confirm password')}
                  <input id="account-confirm-password" name="password_confirmation" type={visible ? 'text' : 'password'} autoComplete="new-password" required minLength={12} maxLength={128} value={confirmation} disabled={auth.isBusy} onChange={(event) => setConfirmation(event.target.value)} /></label></>}
              {error && <p className="auth-error" role="alert">{text(...(errors[error] ?? errors.request_failed))}</p>}
              <button type="submit" className="ew-primary" disabled={auth.isBusy || auth.loading || (registering && !name.trim())}>
                {auth.isBusy ? text('正在处理…', 'Please wait…') : registering ? text('注册并继续', 'Create account and continue') : text('登录并继续', 'Sign in and continue')}<ArrowRight size={16} />
              </button>
              <p className="auth-switch">{registering ? text('已有账户？', 'Already have an account?') : text('还没有账户？', 'New to SecFusion?')} <Link to={switchUrl}>{registering ? text('直接登录', 'Sign in') : text('注册账户', 'Create an account')}</Link></p>
              <small className="auth-session-note"><LockKeyhole size={13} />{text('登录后可继续个人关注与调查。', 'Sign in to return to your interests and investigations.')}</small>
            </form>}
      <Link className="auth-return" to={returnTo}>{text('返回浏览情报', 'Return to intelligence')}</Link>
    </section>
  </main>
}
