import type { SlideshowApi } from '../shared/types'

declare global {
  interface Window {
    slideshow: SlideshowApi
  }
}
