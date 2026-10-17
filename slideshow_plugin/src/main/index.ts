// The plugin process. One run = one slideshow window: the app sends initialize, then
// command.execute, which is answered only when the window closes (so the app greys this
// plugin's menu rows meanwhile, by design), then shutdown.
//
// The image list is read once, here, when the command starts; the renderer sorts and filters
// that list and never asks for it again. Listing reads the app's in-memory tree and does not
// reach MEGA; only loading an image through its stream URL does.

import { app, BrowserWindow, ipcMain, Menu, screen } from 'electron'
import { readFileSync, renameSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { Rpc } from './rpc'
import { extensionOf, IMAGE_EXTENSIONS, Item, mergeSettings, Session, Settings } from '../shared/types'

interface ContextItem {
  handle: string
  name: string
  type: 'file' | 'folder'
  parent: string | null
}

interface ExecuteParams {
  commandId: 'this-folder' | 'subfolders'
  context: { site: string; items: ContextItem[] }
}

interface Page {
  items: Item[]
  nextCursor: string | null
}

// app.exit, not app.quit: quit is ignored before the app is ready, and nothing needs the
// before-quit sequence. The empty write waits for stdout to drain first; on Windows a pipe
// write is asynchronous, and exiting earlier could drop the last response.
function exitAfterFlush(): void {
  process.stdout.write('', () => app.exit(0))
}

const rpc = new Rpc(exitAfterFlush)
let pluginDir = process.cwd()
let settings: Settings = mergeSettings(null)
let session: Promise<Session> | null = null
let window: BrowserWindow | null = null
// streamUrl results by handle. The app's URLs stay valid for the whole run, so an image shown
// twice (looping, going back) needs no second call.
const urls = new Map<string, string>()

function settingsPath(): string {
  return join(pluginDir, 'settings.json')
}

function loadSettings(): Settings {
  try {
    return mergeSettings(JSON.parse(readFileSync(settingsPath(), 'utf8')))
  } catch {
    return mergeSettings(null)
  }
}

function writeSettings(): void {
  // Through a temp file, so being killed mid-write (the app kills plugins on exit or
  // sign-out without notice) cannot leave a truncated settings.json.
  const tmp = settingsPath() + '.tmp'
  try {
    writeFileSync(tmp, JSON.stringify(settings, null, 2))
    renameSync(tmp, settingsPath())
  } catch (error) {
    process.stderr.write(`could not save settings: ${error}\n`)
  }
}

const FIELDS = ['name', 'size', 'mtime', 'path', 'tags']
const SUPPORTED = new Set<string>(IMAGE_EXTENSIONS)

async function listImages(params: ExecuteParams): Promise<Session> {
  const method = params.commandId === 'this-folder' ? 'items.children' : 'items.descendants'
  const folders = params.context.items.filter((item) => item.type === 'folder')
  const seen = new Set<string>()
  const items: Item[] = []
  for (const folder of folders) {
    let cursor: string | null = null
    do {
      const page: Page = await rpc.call<Page>(method, {
        handle: folder.handle,
        type: 'file',
        cursor,
        limit: 1000,
        fields: FIELDS
      })
      for (const item of page.items) {
        if (!seen.has(item.handle) && SUPPORTED.has(extensionOf(item.name))) {
          seen.add(item.handle)
          items.push(item)
        }
      }
      cursor = page.nextCursor
    } while (cursor !== null)
  }
  const scope = folders.map((f) => (f.parent === null ? 'Cloud Drive' : f.name)).join(', ')
  return { scope, items, settings }
}

// Drops a saved position that no longer lies on any display (a monitor was unplugged).
function restoredBounds(): Electron.Rectangle | { width: number; height: number } {
  const { x, y, width, height } = settings.window
  if (x === undefined || y === undefined) return { width, height }
  const visible = screen.getAllDisplays().some((d) => {
    const a = d.workArea
    return x < a.x + a.width && x + width > a.x && y < a.y + a.height && y + height > a.y
  })
  return visible ? { x, y, width, height } : { width, height }
}

function openWindow(title: string, onClosed: () => void): void {
  const win = new BrowserWindow({
    ...restoredBounds(),
    minWidth: 480,
    minHeight: 320,
    title,
    show: false,
    backgroundColor: '#000000',
    titleBarStyle: 'hidden',
    titleBarOverlay: { color: '#000000', symbolColor: '#d4d4d4', height: 36 },
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: true,
      contextIsolation: true
    }
  })
  window = win
  win.once('ready-to-show', () => {
    if (settings.window.maximized) win.maximize()
    win.show()
  })
  win.on('close', () => {
    const b = win.getNormalBounds()
    settings.window = { x: b.x, y: b.y, width: b.width, height: b.height, maximized: win.isMaximized() }
    writeSettings()
  })
  win.on('closed', () => {
    window = null
    onClosed()
  })
  if (process.env.ELECTRON_RENDERER_URL) void win.loadURL(process.env.ELECTRON_RENDERER_URL)
  else void win.loadFile(join(__dirname, '../renderer/index.html'))
}

ipcMain.handle('load-session', () => session)

ipcMain.handle('stream-url', async (_event, handle: string) => {
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

ipcMain.handle('reveal', async (_event, handle: string) => {
  await rpc.call('ui.reveal', { handle })
})

ipcMain.on('save-settings', (_event, next: Settings) => {
  // The window state is the main process's to record; keep it from the renderer's copy.
  settings = { ...mergeSettings(next), window: settings.window }
  writeSettings()
})

ipcMain.on('close', () => window?.close())

rpc.on('initialize', (params) => {
  const dir = (params as { plugin?: { dir?: string } }).plugin?.dir
  if (dir) pluginDir = dir
  settings = loadSettings()
  return { apiVersion: 1 }
})

rpc.on('command.execute', async (params) => {
  const execute = params as ExecuteParams
  await app.whenReady()
  session = listImages(execute)
  // Keeps an unhandled-rejection warning out of the log; the renderer gets the error.
  session.catch(() => {})
  const title = execute.commandId === 'this-folder' ? 'Slideshow' : 'Slideshow (including subfolders)'
  await new Promise<void>((resolve) => openWindow(title, resolve))
  return {}
})

rpc.on('shutdown', () => {
  setImmediate(exitAfterFlush)
  return {}
})

// No Cancel reaches a "progress": "never" command, but answer the notification quietly.
rpc.on('$/cancel', () => {})

Menu.setApplicationMenu(null)
// Closing the window answers command.execute; the process itself ends on shutdown or EOF.
app.on('window-all-closed', () => {})
rpc.start()
