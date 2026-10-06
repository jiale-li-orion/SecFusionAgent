const PRODUCT_PRINCIPAL = 'user:product-demo'

export function productHeaders(extra: Record<string, string> = {}) {
  return { 'X-Principal': PRODUCT_PRINCIPAL, ...extra }
}
