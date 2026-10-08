export type AccountUser = { id: string; email: string; display_name: string }
export type AuthSession = { authenticated: boolean; user: AccountUser | null }
export type LoginInput = { email: string; password: string }
export type RegisterInput = LoginInput & { display_name: string }

export class AccountRequestError extends Error {
  code: string
  status: number

  constructor(code: string, status: number) {
    super(code)
    this.name = 'AccountRequestError'
    this.code = code
    this.status = status
  }
}

async function authRequest(path: string, body?: LoginInput | RegisterInput | Record<string, never>, signal?: AbortSignal): Promise<AuthSession> {
  const response = await fetch(`/api/v1/auth/${path}`, {
    credentials: 'same-origin',
    method: body === undefined ? 'GET' : 'POST',
    signal,
    ...(body === undefined ? {} : {
      headers: { 'Content-Type': 'application/json', 'X-SecFusion-CSRF': '1' },
      body: JSON.stringify(body),
    }),
  })
  if (!response.ok) {
    const problem = await response.json().catch(() => null) as { code?: string } | null
    throw new AccountRequestError(problem?.code ?? 'request_failed', response.status)
  }
  return response.json() as Promise<AuthSession>
}

export function getAccountSession(signal?: AbortSignal) { return authRequest('me', undefined, signal) }
export function loginAccount(input: LoginInput) { return authRequest('login', input) }
export function registerAccount(input: RegisterInput) { return authRequest('register', input) }
export function logoutAccount() { return authRequest('logout', {}) }
