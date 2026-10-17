// Loads images through their stream URLs and keeps the few around the current one decoded.
//
// Each load is one read from MEGA (the app's local server fetches the file as it is
// requested), so prefetching is deliberately sequential — one image at a time, at most
// PREFETCH ahead — rather than parallel: the repo's rule is not to put load on MEGA for speed.
//
// A loaded entry keeps its HTMLImageElement alive. That is what makes the later <img src> with
// the same URL instant: Chromium serves it from the memory cache of a live, decoded image
// instead of requesting it again.

import { Item } from '@shared/types'

export const PREFETCH = 2
const TIMEOUT_MS = 10_000

interface Entry {
  promise: Promise<HTMLImageElement>
  image?: HTMLImageElement
}

export class ImageLoader {
  private entries = new Map<string, Entry>()
  private prefetchToken = 0

  load(item: Item): Promise<HTMLImageElement> {
    const existing = this.entries.get(item.handle)
    if (existing) return existing.promise
    const entry = {} as Entry
    entry.promise = (async () => {
      const url = await window.slideshow.streamUrl(item.handle)
      const image = new Image()
      entry.image = image
      image.src = url
      let timer = 0
      const timeout = new Promise<never>((_, reject) => {
        timer = window.setTimeout(() => reject(new Error('timed out')), TIMEOUT_MS)
      })
      try {
        await Promise.race([image.decode(), timeout])
      } finally {
        window.clearTimeout(timer)
      }
      return image
    })()
    // A failed load is forgotten, so coming back to the image later tries again.
    entry.promise.catch(() => {
      if (this.entries.get(item.handle) === entry) {
        this.release(entry)
        this.entries.delete(item.handle)
      }
    })
    this.entries.set(item.handle, entry)
    return entry.promise
  }

  // Loads the next PREFETCH images one after another; a later call supersedes this chain.
  prefetch(playlist: Item[], index: number): void {
    const token = ++this.prefetchToken
    void (async () => {
      for (let k = 1; k <= PREFETCH && k < playlist.length; k++) {
        if (token !== this.prefetchToken) return
        await this.load(playlist[(index + k) % playlist.length]).catch(() => {})
      }
    })()
  }

  // Frees every image except the current one, the one before it and the prefetched ones.
  keepAround(playlist: Item[], index: number): void {
    const keep = new Set<string>()
    for (let k = -1; k <= PREFETCH; k++) {
      const item = playlist[(index + k + playlist.length) % playlist.length]
      if (item) keep.add(item.handle)
    }
    for (const [handle, entry] of this.entries) {
      if (!keep.has(handle)) {
        this.release(entry)
        this.entries.delete(handle)
      }
    }
  }

  private release(entry: Entry): void {
    // Dropping src aborts a download still in flight and lets Chromium drop the bitmap.
    if (entry.image) entry.image.src = ''
  }
}
