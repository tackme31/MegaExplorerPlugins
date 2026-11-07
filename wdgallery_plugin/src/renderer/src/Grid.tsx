import { useState } from 'react'
import { ImageOff, Play } from 'lucide-react'
import type { Hit } from '../../shared/types'
import { thumbnailUrl } from './format'
import { RATING_COLOURS } from './RatingPanel'

function Thumbnail(props: { hit: Hit }) {
  const [failed, setFailed] = useState(false)
  if (!props.hit.hasThumbnail || failed)
    return (
      <div className="grid h-full w-full place-items-center text-neutral-600">
        <ImageOff size={28} />
      </div>
    )
  return (
    <img
      src={thumbnailUrl(props.hit.handle)}
      loading="lazy"
      draggable={false}
      onError={() => setFailed(true)}
      className="h-full w-full object-cover transition-transform duration-200 group-hover:scale-[1.03]"
    />
  )
}

export function Grid(props: { hits: Hit[]; onOpen: (index: number) => void }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-x-3 gap-y-4">
      {props.hits.map((hit, index) => (
        <button
          key={hit.handle}
          onClick={() => props.onOpen(index)}
          className="group flex min-w-0 flex-col gap-1.5 rounded-lg p-1.5 text-left outline-none hover:bg-white/5 focus-visible:ring-2 focus-visible:ring-sky-500"
        >
          <div className="relative aspect-square w-full overflow-hidden rounded-md bg-neutral-800">
            <Thumbnail hit={hit} />
            {hit.video && (
              <span className="absolute top-1/2 left-1/2 grid h-10 w-10 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-black/55 text-white ring-1 ring-white/30">
                <Play size={18} fill="currentColor" className="ml-0.5" />
              </span>
            )}
            {hit.rating && (
              <span
                className={`absolute top-1.5 right-1.5 h-2 w-2 rounded-full ring-2 ring-black/40 ${RATING_COLOURS[hit.rating]}`}
              />
            )}
            {hit.score !== undefined && (
              <span className="absolute bottom-1.5 left-1.5 rounded bg-black/60 px-1.5 py-0.5 text-[11px] text-violet-100 tabular-nums">
                {(hit.score * 100).toFixed(1)}%
              </span>
            )}
          </div>
          <span title={hit.name} className="truncate px-0.5 text-[13px] text-neutral-300 group-hover:text-white">
            {hit.name}
          </span>
        </button>
      ))}
    </div>
  )
}
