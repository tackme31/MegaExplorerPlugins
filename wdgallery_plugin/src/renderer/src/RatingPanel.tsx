import { Check } from 'lucide-react'
import { type Rating, RATINGS } from '../../shared/types'

export const RATING_COLOURS: Record<Rating, string> = {
  general: 'bg-emerald-400',
  sensitive: 'bg-sky-400',
  questionable: 'bg-amber-400',
  explicit: 'bg-rose-500'
}

export const RATING_LABELS: Record<Rating, string> = {
  general: 'General',
  sensitive: 'Sensitive',
  questionable: 'Questionable',
  explicit: 'Explicit'
}

export function RatingPanel(props: {
  counts: Record<Rating, number>
  selected: Set<Rating>
  onToggle: (r: Rating) => void
  onClear: () => void
}) {
  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-white/5 px-3 py-3">
      <div className="mb-2 flex items-center justify-between px-2">
        <h2 className="text-xs font-semibold tracking-wide text-neutral-400 uppercase">Rating</h2>
        {props.selected.size > 0 && (
          <button onClick={props.onClear} className="text-xs text-neutral-500 hover:text-neutral-200">
            Clear
          </button>
        )}
      </div>
      {RATINGS.map((r) => {
        const on = props.selected.has(r)
        return (
          <button
            key={r}
            onClick={() => props.onToggle(r)}
            className={`flex h-9 items-center gap-2.5 rounded-md px-2 text-left text-sm transition-colors ${
              on ? 'bg-white/10 text-white' : 'text-neutral-300 hover:bg-white/5'
            }`}
          >
            <span
              className={`grid h-4 w-4 shrink-0 place-items-center rounded border ${
                on ? 'border-sky-500 bg-sky-500' : 'border-neutral-500'
              }`}
            >
              {on && <Check size={12} strokeWidth={3} className="text-white" />}
            </span>
            <span className={`h-2 w-2 shrink-0 rounded-full ${RATING_COLOURS[r]}`} />
            <span className="flex-1">{RATING_LABELS[r]}</span>
            <span className="text-xs text-neutral-500 tabular-nums">({props.counts[r].toLocaleString()})</span>
          </button>
        )
      })}
    </aside>
  )
}
