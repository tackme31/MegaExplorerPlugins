// Shapes passed between the renderer, the main process and the index worker.

export const RATINGS = ['general', 'sensitive', 'questionable', 'explicit'] as const
export type Rating = (typeof RATINGS)[number]

export const IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'gif']
export const VIDEO_EXTENSIONS = ['mp4', 'avi', 'mkv', 'webm', 'mov', 'wmv', 'flv', 'm4v']

export function extensionOf(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot < 0 ? '' : name.slice(dot + 1).toLowerCase()
}

export type Condition =
  | { id: number; kind: 'tag'; word: string; negated?: true }
  | { id: number; kind: 'character'; word: string; negated?: true }
  | { id: number; kind: 'name'; text: string }
  | { id: number; kind: 'size'; op: '>' | '<'; bytes: number }
  | { id: number; kind: 'modified'; op: '>' | '<'; date: string }
  | { id: number; kind: 'similar'; handle: string; name: string }

export const SORTS = ['mtime-desc', 'mtime-asc', 'name-asc', 'name-desc', 'size-desc', 'size-asc'] as const
export type Sort = (typeof SORTS)[number]

export interface SearchRequest {
  conditions: Condition[]
  ratings: Rating[]
  sort: Sort
  page: number
  pageSize: number
}

export interface Hit {
  handle: string
  name: string
  size: number
  mtime: number
  rating: Rating | null
  video: boolean
  hasThumbnail: boolean
  score?: number
}

export interface SearchResult {
  total: number
  ratingCounts: Record<Rating, number>
  hits: Hit[]
  page: number
  // The similar-to file is no longer in the index (removed by a rebuild).
  missingReference?: boolean
  millis: number
}

export interface Suggestion {
  word: string
  files: number
}

export interface Detail {
  handle: string
  rating: Rating | null
  characters: string[]
  // WD Tagger's words in its order, then the user's own tags.
  general: string[]
  user: string[]
}

export type IndexStatus =
  | { state: 'ready'; files: number; indexedAt: number }
  | { state: 'building'; read: number; phase: 'reading' | 'writing' }
  | { state: 'error'; message: string }

export interface GalleryApi {
  status(): Promise<IndexStatus>
  onStatus(listener: (status: IndexStatus) => void): void
  rebuild(): void
  search(request: SearchRequest): Promise<SearchResult>
  suggest(kind: 'tag' | 'character', text: string): Promise<Suggestion[]>
  detail(handle: string): Promise<Detail | null>
  path(handle: string): Promise<string>
  streamUrl(handle: string): Promise<string>
  open(handle: string): Promise<void>
  reveal(handle: string): Promise<void>
}
