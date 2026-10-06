/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useMemo, useState } from 'react'

export type ProductLanguage = 'zh' | 'en'

type I18nContextValue = {
  language: ProductLanguage
  setLanguage: (language: ProductLanguage) => void
  text: (zh: string, en: string) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

function initialLanguage(): ProductLanguage {
  if (typeof window === 'undefined') return 'zh'
  const stored = window.localStorage.getItem('secfusion.language')
  if (stored === 'zh' || stored === 'en') return stored
  return navigator.language.toLowerCase().startsWith('zh') ? 'zh' : 'en'
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguage] = useState<ProductLanguage>(initialLanguage)

  useEffect(() => {
    window.localStorage.setItem('secfusion.language', language)
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en'
  }, [language])

  const value = useMemo<I18nContextValue>(() => ({
    language,
    setLanguage,
    text: (zh, en) => language === 'zh' ? zh : en,
  }), [language])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const value = useContext(I18nContext)
  if (!value) throw new Error('useI18n must be used inside I18nProvider')
  return value
}
