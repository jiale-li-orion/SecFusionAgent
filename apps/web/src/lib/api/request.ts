export const UNAUTHORIZED_EVENT = 'secfusion:unauthorized'
let accountSessionEpoch = 0

export function markAccountSessionChanged() {
  accountSessionEpoch += 1
}

export function productHeaders(extra: Record<string, string> = {}) {
  return { 'X-SecFusion-CSRF': '1', ...extra }
}

export async function productFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const epoch = accountSessionEpoch
  const response = await fetch(input, { credentials: 'same-origin', ...init })
  if (response.status === 401 && epoch === accountSessionEpoch) {
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
  }
  return response
}
