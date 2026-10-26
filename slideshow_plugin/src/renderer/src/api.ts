// The bridge to the main process: the preload's window.slideshow inside Electron, or the
// plugin's LAN server (src/main/web.ts) when the page is opened in a phone's browser.

import type { Session, Settings, SlideshowApi } from '@shared/types'

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body)
  })
  const data = (await res.json().catch(() => ({}))) as T & { message?: string }
  if (!res.ok) throw new Error(data.message ?? `HTTP ${res.status}`)
  return data
}

const webApi: SlideshowApi = {
  loadSession: () => request<Session>('GET', '/api/session'),
  streamUrl: async (handle) => `/img/${encodeURIComponent(handle)}`,
  reveal: async (handle) => {
    await request('POST', `/api/reveal/${encodeURIComponent(handle)}`)
  },
  saveSettings: (settings: Settings) => void request('POST', '/api/settings', settings).catch(() => {}),
  close: () => {}
}

export const inBrowser = typeof window.slideshow === 'undefined'
export const api: SlideshowApi = inBrowser ? webApi : window.slideshow
