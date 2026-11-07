import type { GalleryApi } from '../shared/types'

declare global {
  interface Window {
    gallery: GalleryApi
  }
}
