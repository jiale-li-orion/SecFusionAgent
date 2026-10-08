import { Fragment, useCallback, useEffect, useRef, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getAccountSession, loginAccount, logoutAccount, registerAccount,
  type AuthSession, type LoginInput, type RegisterInput,
} from '../../lib/api/auth'
import { AuthContext } from '../../lib/auth'
import { markAccountSessionChanged, UNAUTHORIZED_EVENT } from '../../lib/api/request'

const authKey = ['auth-session']

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const previousIdentity = useRef<string | null | undefined>(undefined)
  const accountChannel = useRef<BroadcastChannel | null>(null)
  const session = useQuery({
    queryKey: authKey,
    queryFn: ({ signal }) => getAccountSession(signal),
    staleTime: 30_000, retry: false, refetchOnWindowFocus: 'always',
  })
  const replaceSession = useCallback(async (next: AuthSession) => {
    markAccountSessionChanged()
    await queryClient.cancelQueries()
    queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== authKey[0] })
    queryClient.getMutationCache().clear()
    previousIdentity.current = next.user?.id ?? null
    queryClient.setQueryData(authKey, next)
    accountChannel.current?.postMessage('account-changed')
  }, [queryClient])
  const login = useMutation({ mutationFn: loginAccount, onSuccess: replaceSession })
  const register = useMutation({ mutationFn: registerAccount, onSuccess: replaceSession })
  const logout = useMutation({ mutationFn: logoutAccount, onSuccess: replaceSession })
  const identity = session.data?.user?.id ?? null

  useEffect(() => {
    if (typeof BroadcastChannel === 'undefined') return
    const channel = new BroadcastChannel('secfusion-account')
    accountChannel.current = channel
    channel.onmessage = () => {
      void queryClient.invalidateQueries({ queryKey: authKey })
    }
    return () => { accountChannel.current = null; channel.close() }
  }, [queryClient])

  useEffect(() => {
    const expired = () => { void replaceSession({ authenticated: false, user: null }) }
    window.addEventListener(UNAUTHORIZED_EVENT, expired)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, expired)
  }, [replaceSession])

  useEffect(() => {
    if (!session.data) return
    if (previousIdentity.current !== undefined && previousIdentity.current !== identity) {
      // Another tab can replace or end the same cookie session.
      markAccountSessionChanged()
      void queryClient.cancelQueries({ predicate: (query) => query.queryKey[0] !== authKey[0] })
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== authKey[0] })
      queryClient.getMutationCache().clear()
    }
    previousIdentity.current = identity
  }, [identity, queryClient, session.data])

  return <AuthContext.Provider value={{
    user: session.data?.user ?? null,
    authenticated: Boolean(session.data?.authenticated && session.data.user),
    loading: session.isPending,
    isBusy: login.isPending || register.isPending || logout.isPending,
    error: session.error,
    refresh: async () => { await session.refetch() },
    login: (input: LoginInput) => login.mutateAsync(input),
    register: (input: RegisterInput) => register.mutateAsync(input),
    logout: () => logout.mutateAsync(),
  }}>
    <Fragment key={identity ?? 'guest'}>{children}</Fragment>
  </AuthContext.Provider>
}
