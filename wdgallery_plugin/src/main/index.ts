// The plugin process. One run = one window: the app sends initialize, then command.execute,
// which is answered only when the window closes (so the app greys this plugin's menu rows
// meanwhile, by design), then shutdown.
//
// The index lives in a file per Cloud Drive root (one per account), reused across runs and
// replaced only by Rebuild. Reading the drive goes through items.descendants, which reads the
// app's memory and does not reach MEGA; thumbnails, previews and stream URLs do, so they are
// fetched only for what is on screen, a few at a time.

import { app, BrowserWindow, ipcMain, Menu, protocol } from 'electron'
import { mkdirSync, readFileSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { Worker } from 'node:worker_threads'
import workerPath from './worker?modulePath'
import { Rpc, RpcError } from './rpc'
import type { RawItem } from './store'
import type { WorkerRequest } from './worker'
import {
  extensionOf,
  IMAGE_EXTENSIONS,
  type IndexStatus,
  type SearchRequest,
  VIDEO_EXTENSIONS
} from '../shared/types'

const BACKGROUND = '#171717'
const FIELDS = ['name', 'size', 'mtime', 'tags', 'hasThumbnail', 'crc']
const MEDIA = new Set([...IMAGE_EXTENSIONS, ...VIDEO_EXTENSIONS])
const NOT_FOUND = -32002
const THUMBNAILS_IN_FLIGHT = 3
const THUMBNAIL_CACHE = 600
const PREVIEW_CACHE = 20

interface ContextItem {
  handle: string
  parent: string | null
}

// app.exit, not app.quit: quit is ignored before the app is ready. The empty write waits for
// stdout to drain first; on Windows a pipe write is asynchronous.
function exitAfterFlush(): void {
  process.stdout.write('', () => app.exit(0))
}

const rpc = new Rpc(exitAfterFlush)
let window: BrowserWindow | null = null
let indexPath = ''
let status: IndexStatus = { state: 'building', read: 0, phase: 'reading' }
let building = false
let rootHandle = ''
const urls = new Map<string, string>()

// --- the index worker ------------------------------------------------------------------

class IndexWorker {
  private readonly worker = new Worker(workerPath)
  private readonly pending = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }>()
  private nextId = 1

  constructor() {
    this.worker.on('message', ({ id, result, error }: { id: number; result?: unknown; error?: string }) => {
      const p = this.pending.get(id)
      this.pending.delete(id)
      if (error !== undefined) p?.reject(new Error(error))
      else p?.resolve(result)
    })
  }

  call<T>(message: WorkerRequest): Promise<T> {
    const id = this.nextId++
    return new Promise<T>((resolve, reject) => {
      this.pending.set(id, { resolve: resolve as (v: unknown) => void, reject })
      this.worker.postMessage({ id, message })
    })
  }

  terminate(): void {
    void this.worker.terminate()
  }
}

let index: IndexWorker | null = null

function setStatus(next: IndexStatus): void {
  status = next
  window?.webContents.send('status', next)
}

function readyStatus(meta: Record<string, string>): IndexStatus {
  return { state: 'ready', files: Number(meta.files), indexedAt: Number(meta.indexedAt) }
}

async function rebuild(): Promise<void> {
  if (building || !index) return
  building = true
  try {
    setStatus({ state: 'building', read: 0, phase: 'reading' })
    await index.call({ op: 'build-start' })
    let cursor: string | null = null
    let read = 0
    do {
      const page: { items: RawItem[]; nextCursor: string | null } = await rpc.call('items.descendants', {
        handle: rootHandle,
        type: 'file',
        cursor,
        limit: 1000,
        fields: FIELDS
      })
      const media = page.items.filter((item) => MEDIA.has(extensionOf(item.name)))
      if (media.length) read = await index.call<number>({ op: 'build-add', items: media })
      setStatus({ state: 'building', read, phase: 'reading' })
      cursor = page.nextCursor
    } while (cursor !== null)
    setStatus({ state: 'building', read, phase: 'writing' })
    const meta = await index.call<Record<string, string>>({
      op: 'build-finish',
      path: indexPath,
      meta: { root: rootHandle, indexedAt: String(Date.now()) }
    })
    setStatus(readyStatus(meta))
  } catch (error) {
    process.stderr.write(`rebuild failed: ${error}\n`)
    setStatus({ state: 'error', message: error instanceof Error ? error.message : String(error) })
  } finally {
    building = false
  }
}

// The Cloud Drive (or other) root above the clicked item: the index is kept per root.
async function findRoot(item: ContextItem): Promise<string> {
  let handle = item.handle
  let parent = item.parent
  while (parent !== null) {
    handle = parent
    const result = await rpc.call<{ items: { parent: string | null }[] }>('items.get', {
      handles: [handle],
      fields: ['parent']
    })
    parent = result.items[0].parent
  }
  return handle
}

function indexFileFor(root: string): string {
  const dir = join(process.env.LOCALAPPDATA ?? app.getPath('userData'), 'MegaExplorer-WDGallery')
  mkdirSync(dir, { recursive: true })
  return join(dir, `${root.replace(/[^A-Za-z0-9_-]/g, '_')}.sqlite`)
}

// --- thumbnails and previews -----------------------------------------------------------

class Limiter {
  private running = 0
  private readonly waiting: (() => void)[] = []

  constructor(private readonly max: number) {}

  async run<T>(task: () => Promise<T>): Promise<T> {
    if (this.running >= this.max) await new Promise<void>((resolve) => this.waiting.push(resolve))
    this.running++
    try {
      return await task()
    } finally {
      this.running--
      this.waiting.shift()?.()
    }
  }
}

function remember(cache: Map<string, Buffer>, key: string, value: Buffer, max: number): void {
  cache.delete(key)
  cache.set(key, value)
  if (cache.size > max) cache.delete(cache.keys().next().value!)
}

// The file the app saved is ours to delete once read.
async function fetchImage(method: string, handle: string): Promise<Buffer> {
  const { path } = await rpc.call<{ path: string }>(method, { handle })
  const data = readFileSync(path)
  rmSync(path, { force: true })
  return data
}

const thumbnails = new Map<string, Buffer>()
const previews = new Map<string, Buffer>()
const limiter = new Limiter(THUMBNAILS_IN_FLIGHT)

async function thumbnail(handle: string, signal?: AbortSignal): Promise<Buffer | null> {
  const cached = thumbnails.get(handle)
  if (cached) return cached
  return limiter.run(async () => {
    // Scrolled or paged away while queued: skip the download.
    if (signal?.aborted) return null
    const data = await fetchImage('items.fetchThumbnail', handle)
    remember(thumbnails, handle, data, THUMBNAIL_CACHE)
    return data
  })
}

async function preview(handle: string): Promise<Buffer | null> {
  const cached = previews.get(handle)
  if (cached) return cached
  try {
    const data = await fetchImage('items.fetchPreview', handle)
    remember(previews, handle, data, PREVIEW_CACHE)
    return data
  } catch (error) {
    if (error instanceof RpcError && error.code === NOT_FOUND) return thumbnail(handle)
    throw error
  }
}

function imageResponse(data: Buffer | null): Response {
  if (!data) return new Response(null, { status: 404 })
  return new Response(new Uint8Array(data), { headers: { 'content-type': 'image/jpeg' } })
}

function handleOf(request: Request): string {
  return decodeURIComponent(new URL(request.url).pathname.slice(1))
}

protocol.registerSchemesAsPrivileged([
  { scheme: 'thumb', privileges: { standard: true, secure: true, supportFetchAPI: true } },
  { scheme: 'preview', privileges: { standard: true, secure: true, supportFetchAPI: true } }
])

function registerProtocols(): void {
  protocol.handle('thumb', (request) =>
    thumbnail(handleOf(request), request.signal).then(imageResponse, () => imageResponse(null))
  )
  protocol.handle('preview', (request) => preview(handleOf(request)).then(imageResponse, () => imageResponse(null)))
}

// --- the window and its requests -------------------------------------------------------

function openWindow(onClosed: () => void): void {
  const win = new BrowserWindow({
    width: 1320,
    height: 860,
    minWidth: 760,
    minHeight: 480,
    title: 'WD Gallery',
    show: false,
    backgroundColor: BACKGROUND,
    titleBarStyle: 'hidden',
    titleBarOverlay: { color: BACKGROUND, symbolColor: '#d4d4d4', height: 36 },
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: true,
      contextIsolation: true
    }
  })
  window = win
  win.once('ready-to-show', () => win.show())
  win.on('closed', () => {
    window = null
    onClosed()
  })
  if (process.env.ELECTRON_RENDERER_URL) void win.loadURL(process.env.ELECTRON_RENDERER_URL)
  else void win.loadFile(join(__dirname, '../renderer/index.html'))
}

function worker(): IndexWorker {
  if (!index) throw new Error('No index')
  return index
}

ipcMain.handle('status', () => status)
ipcMain.on('rebuild', () => void rebuild())
ipcMain.handle('search', (_e, request: SearchRequest) => worker().call({ op: 'search', request }))
ipcMain.handle('suggest', (_e, kind: 'tag' | 'character', text: string) => worker().call({ op: 'suggest', kind, text }))
ipcMain.handle('detail', (_e, handle: string) => worker().call({ op: 'detail', handle }))
ipcMain.handle('path', async (_e, handle: string) => {
  const result = await rpc.call<{ items: { path: string }[] }>('items.get', { handles: [handle], fields: ['path'] })
  return result.items[0].path
})
ipcMain.handle('stream-url', async (_e, handle: string) => {
  const cached = urls.get(handle)
  if (cached) return cached
  const result = await rpc.call<{ urls: { url?: string; error?: { message: string } }[] }>('items.streamUrl', {
    handles: [handle]
  })
  const entry = result.urls[0]
  if (!entry?.url) throw new Error(entry?.error?.message ?? 'No URL')
  urls.set(handle, entry.url)
  return entry.url
})
ipcMain.handle('open', async (_e, handle: string) => {
  await rpc.call('ui.open', { handle })
})
ipcMain.handle('reveal', async (_e, handle: string) => {
  await rpc.call('ui.reveal', { handle })
})

rpc.on('initialize', () => ({ apiVersion: 2 }))

rpc.on('command.execute', async (params) => {
  const items = (params as { context?: { items?: ContextItem[] } }).context?.items ?? []
  if (!items.length) throw new Error('Nothing was selected to find the drive from.')
  await app.whenReady()
  registerProtocols()
  rootHandle = await findRoot(items[0])
  indexPath = indexFileFor(rootHandle)
  index = new IndexWorker()
  const meta = await index.call<Record<string, string> | null>({ op: 'open', path: indexPath })
  if (meta) status = readyStatus(meta)
  await new Promise<void>((resolve) => {
    openWindow(resolve)
    if (!meta) void rebuild()
  })
  index.terminate()
  index = null
  return {}
})

rpc.on('shutdown', () => {
  setImmediate(exitAfterFlush)
  return {}
})

// No Cancel reaches a "progressDialog": false command, but answer the notification quietly.
rpc.on('$/cancel', () => {})

Menu.setApplicationMenu(null)
// Closing the window answers command.execute; the process itself ends on shutdown or EOF.
app.on('window-all-closed', () => {})
rpc.start()
