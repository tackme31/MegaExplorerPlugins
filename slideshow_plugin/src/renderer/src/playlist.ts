// Filtering and ordering of the list read at start. Pure, so App can recompute it on every
// settings change without touching MEGA.

import { extensionOf, Filters, Item, SortKey } from '@shared/types'

const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })

function startOfDay(iso: string): number {
  return new Date(`${iso}T00:00:00`).getTime() / 1000
}

export function matches(item: Item, f: Filters): boolean {
  if (f.favouritesOnly && !item.favourite) return false
  if (f.nameContains && !item.name.toLowerCase().includes(f.nameContains.toLowerCase())) return false
  if (f.extensionsExcluded.includes(extensionOf(item.name))) return false
  if (f.tagsInclude.length || f.tagsExclude.length) {
    const tags = item.tags.map((t) => t.toLowerCase())
    const has = (term: string): boolean => tags.some((t) => t.includes(term.toLowerCase()))
    if (!f.tagsInclude.every(has)) return false
    if (f.tagsExclude.some(has)) return false
  }
  if (f.modifiedFrom && item.mtime < startOfDay(f.modifiedFrom)) return false
  if (f.modifiedTo && item.mtime >= startOfDay(f.modifiedTo) + 86400) return false
  const mb = item.size / (1024 * 1024)
  if (f.minSizeMB !== null && mb < f.minSizeMB) return false
  if (f.maxSizeMB !== null && mb > f.maxSizeMB) return false
  return true
}

// Deterministic for a given seed, so the shuffled order holds still while the user changes
// unrelated settings; App changes the seed once per lap.
function shuffle<T>(list: T[], seed: number): T[] {
  const out = list.slice()
  let s = seed >>> 0 || 1
  for (let i = out.length - 1; i > 0; i--) {
    s ^= s << 13
    s ^= s >>> 17
    s ^= s << 5
    const j = (s >>> 0) % (i + 1)
    ;[out[i], out[j]] = [out[j], out[i]]
  }
  return out
}

export function buildPlaylist(items: Item[], filters: Filters, key: SortKey, descending: boolean, seed: number): Item[] {
  const kept = items.filter((item) => matches(item, filters))
  if (key === 'random') return shuffle(kept, seed)
  const compare: (a: Item, b: Item) => number =
    key === 'name'
      ? (a, b) => collator.compare(a.name, b.name)
      : key === 'path'
        ? (a, b) => collator.compare(a.path, b.path)
        : key === 'mtime'
          ? (a, b) => a.mtime - b.mtime || collator.compare(a.name, b.name)
          : (a, b) => a.size - b.size || collator.compare(a.name, b.name)
  kept.sort(compare)
  return descending ? kept.reverse() : kept
}

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatDate(mtime: number): string {
  const d = new Date(mtime * 1000)
  const pad = (n: number): string => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const TAG_MAX = 20

export function shortTag(tag: string): string {
  return tag.length > TAG_MAX ? `${tag.slice(0, TAG_MAX)}…` : tag
}
