import { createContext, useContext } from 'react'
import type { AccountUser, AuthSession, LoginInput, RegisterInput } from './api/auth'

export type AuthContextValue = {
  user: AccountUser | null
  authenticated: boolean
  loading: boolean
  isBusy: boolean
  error: Error | null
  refresh: () => Promise<void>
  login: (input: LoginInput) => Promise<AuthSession>
  register: (input: RegisterInput) => Promise<AuthSession>
  logout: () => Promise<AuthSession>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth requires AuthProvider')
  return value
}

export function safeAccountReturnTo(value: string | null | undefined): string {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.includes('\\')
    || [...value].some((character) => character.charCodeAt(0) < 32 || character.charCodeAt(0) === 127)) return '/'
  try {
    const url = new URL(value, 'https://secfusion.local')
    if (url.origin !== 'https://secfusion.local' || /^\/auth(?:\/|$)/.test(url.pathname)) return '/'
    return `${url.pathname}${url.search}${url.hash}`
  } catch { return '/' }
}
