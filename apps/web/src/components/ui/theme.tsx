/* eslint-disable react-refresh/only-export-components -- Theme context and its hook form one UI contract. */
import { createContext, useContext, type ReactNode } from 'react'

const UiThemeContext = createContext<'light' | 'dark'>('light')

/** Context only: callers apply the class to their surface; portals retain the same theme. */
export function UiThemeProvider({ theme, children }: { theme: 'light' | 'dark'; children: ReactNode }) {
  return <UiThemeContext.Provider value={theme}>{children}</UiThemeContext.Provider>
}

export function useUiThemeClass() {
  return useContext(UiThemeContext) === 'dark' ? 'ui-night dark' : 'ui-day'
}
