// Types shared by the main process, the preload bridge and the renderer.

// The subset of MEGA Explorer's Item the slideshow asks for (items.children / descendants
// with `fields`). `handle` is always present; mtime is Unix seconds.
export interface Item {
  handle: string
  name: string
  size: number
  mtime: number
  path: string
  tags: string[]
  favourite: boolean
}

export type SortKey = 'name' | 'mtime' | 'size' | 'path' | 'random'
export type Transition = 'none' | 'fade' | 'slide' | 'zoom'
export type Fit = 'contain' | 'cover' | 'actual'
export type AtEnd = 'loop' | 'stop' | 'close'

export interface Filters {
  favouritesOnly: boolean
  nameContains: string
  // Terms, each matching any tag that contains it, ignoring case: tags can be long (a tagger
  // plugin writes whole phrases), so an exact match would be impractical to type.
  tagsInclude: string[]
  tagsExclude: string[]
  // Lower-case extensions to leave out; an empty list keeps every supported one.
  extensionsExcluded: string[]
  // ISO dates (yyyy-mm-dd), inclusive, or '' for no bound.
  modifiedFrom: string
  modifiedTo: string
  // Megabytes, or null for no bound.
  minSizeMB: number | null
  maxSizeMB: number | null
}

export interface WindowState {
  x?: number
  y?: number
  width: number
  height: number
  maximized: boolean
}

// Everything persisted in settings.json. Loaded with defaults filled in, so an older file
// missing a key still works; see mergeSettings.
export interface Settings {
  intervalSec: number
  transition: Transition
  transitionMs: number
  fit: Fit
  atEnd: AtEnd
  sortKey: SortKey
  sortDescending: boolean
  filters: Filters
  // The bar along the bottom edge that shrinks until the next image.
  showCountdown: boolean
  window: WindowState
}

export const DEFAULT_SETTINGS: Settings = {
  intervalSec: 5,
  transition: 'fade',
  transitionMs: 600,
  fit: 'contain',
  atEnd: 'loop',
  sortKey: 'name',
  sortDescending: false,
  filters: {
    favouritesOnly: false,
    nameContains: '',
    tagsInclude: [],
    tagsExclude: [],
    extensionsExcluded: [],
    modifiedFrom: '',
    modifiedTo: '',
    minSizeMB: null,
    maxSizeMB: null
  },
  showCountdown: true,
  window: { width: 1280, height: 800, maximized: false }
}

// What a browser engine can show, and so what the slideshow lists. HEIC, TIFF, RAW and PSD
// are images to MEGA but Chromium cannot decode them; SVG is left out on purpose.
export const IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp', 'gif', 'avif', 'bmp'] as const

export function extensionOf(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot < 0 ? '' : name.slice(dot + 1).toLowerCase()
}

export function mergeSettings(raw: unknown): Settings {
  const s = (raw && typeof raw === 'object' ? raw : {}) as Partial<Settings>
  return {
    ...DEFAULT_SETTINGS,
    ...s,
    filters: { ...DEFAULT_SETTINGS.filters, ...(s.filters ?? {}) },
    window: { ...DEFAULT_SETTINGS.window, ...(s.window ?? {}) }
  }
}

export interface Session {
  // The folders the command was run on, by name, for the empty-state message.
  scope: string
  items: Item[]
  settings: Settings
}

// The bridge the preload script exposes as window.slideshow.
export interface SlideshowApi {
  // Resolves once the listing is done; rejects with the reason it failed.
  loadSession(): Promise<Session>
  // A local http:// URL for the image, valid while this window is open. Rejects when the
  // item cannot be served (gone since the listing).
  streamUrl(handle: string): Promise<string>
  reveal(handle: string): Promise<void>
  saveSettings(settings: Settings): void
  close(): void
}
