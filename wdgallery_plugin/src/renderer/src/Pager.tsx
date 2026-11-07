import { ChevronLeft, ChevronRight } from 'lucide-react'

// Page numbers to show: the first, the last, and two either side of the current one.
function pageList(current: number, count: number): (number | null)[] {
  const pages: (number | null)[] = []
  for (let p = 0; p < count; p++) {
    if (p === 0 || p === count - 1 || Math.abs(p - current) <= 2) pages.push(p)
    else if (pages[pages.length - 1] !== null) pages.push(null)
  }
  return pages
}

export function Pager(props: { page: number; pageCount: number; onPage: (page: number) => void }) {
  if (props.pageCount <= 1) return null
  const button = 'grid h-8 min-w-8 place-items-center rounded-md px-2 text-sm tabular-nums'
  return (
    <nav className="flex items-center justify-center gap-1 border-t border-white/5 py-2.5">
      <button
        disabled={props.page === 0}
        onClick={() => props.onPage(props.page - 1)}
        className={`${button} text-neutral-300 hover:bg-white/10 disabled:opacity-30 disabled:hover:bg-transparent`}
      >
        <ChevronLeft size={16} />
      </button>
      {pageList(props.page, props.pageCount).map((p, i) =>
        p === null ? (
          <span key={`gap${i}`} className="px-1 text-neutral-500">
            …
          </span>
        ) : (
          <button
            key={p}
            onClick={() => props.onPage(p)}
            className={`${button} ${p === props.page ? 'bg-sky-600 text-white' : 'text-neutral-300 hover:bg-white/10'}`}
          >
            {p + 1}
          </button>
        )
      )}
      <button
        disabled={props.page === props.pageCount - 1}
        onClick={() => props.onPage(props.page + 1)}
        className={`${button} text-neutral-300 hover:bg-white/10 disabled:opacity-30 disabled:hover:bg-transparent`}
      >
        <ChevronRight size={16} />
      </button>
    </nav>
  )
}
