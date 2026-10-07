const PRODUCT_PRINCIPAL = import.meta.env.VITE_SECFUSION_PRINCIPAL || 'user:local'

export function productHeaders(extra: Record<string, string> = {}) {
  return { 'X-Principal': PRODUCT_PRINCIPAL, ...extra }
}
