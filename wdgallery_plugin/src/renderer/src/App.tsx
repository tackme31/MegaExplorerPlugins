// The one screen. Every change to the conditions, ratings, sort or page asks the index for one
// page; answers to superseded requests are dropped.

import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, ArrowDownUp, Loader2, RefreshCw } from 'lucide-react'
import type { Condition, Hit, IndexStatus, Rating, SearchResult, Sort } from '../../shared/types'
import { toggleNegated, withCondition, newId } from './conditions'
import { formatDate } from './format'
import { Grid } from './Grid'
import { Pager } from './Pager'
import { PreviewDialog } from './PreviewDialog'
import { RatingPanel } from './RatingPanel'
import { SearchBar } from './SearchBar'

const PAGE_SIZE = 60

const SORT_LABELS: Record<Sort, string> = {
  'mtime-desc': 'Modified (newest)',
  'mtime-asc': 'Modified (oldest)',
  'name-asc': 'Name (A–Z)',
  'name-desc': 'Name (Z–A)',
  'size-desc': 'Size (largest)',
  'size-asc': 'Size (smallest)'
}

const NO_COUNTS: Record<Rating, number> = { general: 0, sensitive: 0, questionable: 0, explicit: 0 }

function BuildingPanel(props: { status: IndexStatus }) {
  const s = props.status
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 text-neutral-300">
      {s.state === 'building' ? (
        <>
          <Loader2 size={30} className="animate-spin text-sky-400" />
          <p className="text-base">{s.phase === 'reading' ? 'Reading the files from MEGA Explorer…' : 'Writing the index…'}</p>
          <p className="text-sm text-neutral-500 tabular-nums">{s.read.toLocaleString()} images and videos</p>
        </>
      ) : s.state === 'error' ? (
        <>
          <AlertTriangle size={30} className="text-rose-400" />
          <p className="text-base">Could not build the index</p>
          <p className="selectable max-w-xl text-center text-sm text-neutral-500">{s.message}</p>
          <button onClick={() => window.gallery.rebuild()} className="mt-2 rounded-md bg-sky-600 px-4 py-1.5 text-sm text-white hover:bg-sky-500">
            Try again
          </button>
        </>
      ) : null}
    </div>
  )
}

export function App() {
  const [status, setStatus] = useState<IndexStatus | null>(null)
  const [conditions, setConditions] = useState<Condition[]>([])
  const [ratings, setRatings] = useState<Set<Rating>>(new Set())
  const [sort, setSort] = useState<Sort>('mtime-desc')
  const [page, setPage] = useState(0)
  const [result, setResult] = useState<SearchResult | null>(null)
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [openIndex, setOpenIndex] = useState<number | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const scroller = useRef<HTMLDivElement>(null)
  const sequence = useRef(0)
  const lastOpen = useRef<Hit | null>(null)

  useEffect(() => {
    window.gallery.onStatus(setStatus)
    void window.gallery.status().then(setStatus)
  }, [])

  const ready = status?.state === 'ready'
  const indexedAt = status?.state === 'ready' ? status.indexedAt : 0

  useEffect(() => {
    setPage(0)
  }, [conditions, ratings, sort])

  useEffect(() => {
    if (!ready) return
    const id = ++sequence.current
    setSearching(true)
    window.gallery
      .search({ conditions, ratings: [...ratings], sort, page, pageSize: PAGE_SIZE })
      .then(
        (r) => {
          if (id !== sequence.current) return
          setResult(r)
          setSearchError(null)
        },
        (e: Error) => id === sequence.current && setSearchError(e.message)
      )
      .finally(() => id === sequence.current && setSearching(false))
  }, [ready, indexedAt, conditions, ratings, sort, page])

  // Braces matter: Chromium's scrollTo() now returns a Promise, which React would call as cleanup.
  useEffect(() => {
    void scroller.current?.scrollTo({ top: 0 })
  }, [result?.page, conditions, ratings, sort])

  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(null), 3000)
    return () => clearTimeout(timer)
  }, [toast])

  const similar = conditions.find((c) => c.kind === 'similar')
  const total = result?.total ?? 0
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const shownPage = result?.page ?? 0

  // While stepping across a page boundary the new page is still loading; keep showing the last file.
  const openHit =
    openIndex === null
      ? null
      : result && Math.floor(openIndex / PAGE_SIZE) === result.page
        ? (result.hits[openIndex % PAGE_SIZE] ?? null)
        : lastOpen.current
  lastOpen.current = openHit

  function add(c: Condition) {
    setConditions((list) => withCondition(list, c))
    setOpenIndex(null)
  }

  function toggleRating(r: Rating) {
    setRatings((set) => {
      const next = new Set(set)
      if (next.has(r)) next.delete(r)
      else next.add(r)
      return next
    })
  }

  function step(delta: number) {
    if (openIndex === null) return
    const next = openIndex + delta
    if (next < 0 || next >= total) return
    setOpenIndex(next)
    const nextPage = Math.floor(next / PAGE_SIZE)
    if (nextPage !== page) setPage(nextPage)
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="drag flex h-9 shrink-0 items-center gap-3 pr-[150px] pl-4">
        <span className="text-[13px] font-medium text-neutral-300">WD Gallery</span>
        <div className="flex-1" />
        <span className="text-xs text-neutral-500">
          {status?.state === 'ready'
            ? `Indexed ${formatDate(status.indexedAt)} · ${status.files.toLocaleString()} files`
            : status?.state === 'building'
              ? 'Building the index…'
              : ''}
        </span>
        <button
          onClick={() => window.gallery.rebuild()}
          disabled={status?.state === 'building'}
          title="Read the drive again and replace the index"
          className="no-drag flex h-6 items-center gap-1.5 rounded px-2 text-xs text-neutral-300 hover:bg-white/10 disabled:opacity-50"
        >
          {status?.state === 'building' ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />} Rebuild
        </button>
      </header>

      <div className="shrink-0 px-4 pt-1 pb-3">
        <SearchBar
          conditions={conditions}
          onAdd={add}
          onRemove={(id) => setConditions((list) => list.filter((c) => c.id !== id))}
          onToggle={(id) => setConditions((list) => toggleNegated(list, id))}
          onClear={() => setConditions([])}
        />
      </div>

      <div className="flex min-h-0 flex-1 border-t border-white/5">
        <RatingPanel
          counts={result?.ratingCounts ?? NO_COUNTS}
          selected={ratings}
          onToggle={toggleRating}
          onClear={() => setRatings(new Set())}
        />

        <main className="flex min-w-0 flex-1 flex-col">
          {!ready && status ? (
            <BuildingPanel status={status} />
          ) : (
            <>
              <div className="flex h-11 shrink-0 items-center gap-3 px-4">
                <span className="text-sm text-neutral-300">
                  <span className="font-semibold text-white tabular-nums">{total.toLocaleString()}</span> files
                  {total > 0 && (
                    <span className="ml-2 text-neutral-500 tabular-nums">
                      {(shownPage * PAGE_SIZE + 1).toLocaleString()}–{Math.min(total, (shownPage + 1) * PAGE_SIZE).toLocaleString()}
                    </span>
                  )}
                </span>
                {searching ? (
                  <Loader2 size={15} className="animate-spin text-neutral-400" />
                ) : (
                  result && <span className="text-xs text-neutral-600 tabular-nums">{(result.millis / 1000).toFixed(2)} s</span>
                )}
                <div className="flex-1" />
                <label className="flex items-center gap-2 text-[13px] text-neutral-400">
                  <ArrowDownUp size={14} />
                  {similar ? (
                    <span title="A similarity search is always in similarity order" className="text-violet-300">
                      Similarity
                    </span>
                  ) : (
                    <select
                      value={sort}
                      onChange={(e) => setSort(e.target.value as Sort)}
                      className="h-7 rounded-md bg-neutral-800 px-2 text-neutral-200 ring-1 ring-white/10 outline-none"
                    >
                      {Object.entries(SORT_LABELS).map(([key, label]) => (
                        <option key={key} value={key}>
                          {label}
                        </option>
                      ))}
                    </select>
                  )}
                </label>
              </div>

              <div ref={scroller} className={`min-h-0 flex-1 overflow-y-auto px-3 pb-4 transition-opacity ${searching ? 'opacity-60' : ''}`}>
                {searchError ? (
                  <p className="selectable mt-20 text-center text-sm text-rose-300">Search failed: {searchError}</p>
                ) : result?.missingReference ? (
                  <p className="mt-20 text-center text-sm text-neutral-500">The file searched from is no longer in the index.</p>
                ) : result && result.hits.length ? (
                  <Grid hits={result.hits} onOpen={(i) => setOpenIndex(shownPage * PAGE_SIZE + i)} />
                ) : result ? (
                  <p className="mt-20 text-center text-sm text-neutral-500">No files match.</p>
                ) : null}
              </div>
              <Pager page={shownPage} pageCount={pageCount} onPage={setPage} />
            </>
          )}
        </main>
      </div>

      {openHit && openIndex !== null && (
        <PreviewDialog
          hit={openHit}
          position={`${(openIndex + 1).toLocaleString()} / ${total.toLocaleString()}`}
          hasPrevious={openIndex > 0}
          hasNext={openIndex < total - 1}
          onPrevious={() => step(-1)}
          onNext={() => step(1)}
          onClose={() => setOpenIndex(null)}
          onFindSimilar={() => add({ id: newId(), kind: 'similar', handle: openHit.handle, name: openHit.name })}
          onAddTag={(word) => add({ id: newId(), kind: 'tag', word })}
          onAddCharacter={(word) => add({ id: newId(), kind: 'character', word })}
          onError={setToast}
        />
      )}

      {toast && (
        <div className="pointer-events-none fixed bottom-14 left-1/2 z-[60] -translate-x-1/2 rounded-lg bg-neutral-700 px-4 py-2 text-sm text-white shadow-lg">
          {toast}
        </div>
      )}
    </div>
  )
}
