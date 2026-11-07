import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, ExternalLink, FolderOpen, Loader2, Sparkles, X } from 'lucide-react'
import type { Detail, Hit } from '../../shared/types'
import { formatDate, formatSize, previewUrl, thumbnailUrl } from './format'
import { RATING_COLOURS, RATING_LABELS } from './RatingPanel'

function Row(props: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[84px_1fr] gap-2 py-1.5 text-[13px]">
      <dt className="text-neutral-500">{props.label}</dt>
      <dd className="selectable min-w-0 break-all text-neutral-200">{props.children}</dd>
    </div>
  )
}

function TagChip(props: { text: string; onClick: () => void; tone?: 'character' | 'user' }) {
  const tone =
    props.tone === 'character'
      ? 'bg-fuchsia-500/15 text-fuchsia-200 hover:bg-fuchsia-500/30'
      : props.tone === 'user'
        ? 'bg-sky-500/15 text-sky-200 hover:bg-sky-500/30'
        : 'bg-white/8 text-neutral-300 hover:bg-white/15 hover:text-white'
  return (
    <button onClick={props.onClick} title="Add to the search" className={`rounded px-2 py-0.5 text-[12px] transition-colors ${tone}`}>
      {props.text}
    </button>
  )
}

function Spinner(props: { text: string }) {
  return (
    <div className="flex flex-col items-center gap-2 text-sm text-neutral-400">
      <Loader2 size={26} className="animate-spin" /> {props.text}
    </div>
  )
}

// A video plays from its stream URL, asked for when the popup shows it.
function VideoPlayer(props: { handle: string }) {
  const [state, setState] = useState<{ url?: string; error?: string }>({})
  useEffect(() => {
    let live = true
    setState({})
    window.gallery.streamUrl(props.handle).then(
      (url) => live && setState({ url }),
      (e: Error) => live && setState({ error: e.message })
    )
    return () => {
      live = false
    }
  }, [props.handle])
  if (state.error) return <p className="text-sm text-rose-300">Could not play: {state.error}</p>
  if (!state.url) return <Spinner text="Getting the stream URL…" />
  return <video key={props.handle} src={state.url} controls autoPlay loop className="max-h-full max-w-full" />
}

// The thumbnail stands in, blurred, until the preview (about 1000 px) has arrived.
function PreviewImage(props: { hit: Hit }) {
  const [loaded, setLoaded] = useState(false)
  useEffect(() => setLoaded(false), [props.hit.handle])
  return (
    <>
      {!loaded && props.hit.hasThumbnail && (
        <img src={thumbnailUrl(props.hit.handle)} className="absolute inset-0 m-auto max-h-full max-w-full scale-95 opacity-40 blur-md" />
      )}
      {!loaded && (
        <div className="absolute inset-0 grid place-items-center">
          <Spinner text="Loading the preview…" />
        </div>
      )}
      <img
        key={props.hit.handle}
        src={previewUrl(props.hit.handle)}
        draggable={false}
        onLoad={() => setLoaded(true)}
        onError={() => setLoaded(true)}
        className={`max-h-full max-w-full object-contain ${loaded ? '' : 'invisible'}`}
      />
    </>
  )
}

export function PreviewDialog(props: {
  hit: Hit
  position: string
  hasPrevious: boolean
  hasNext: boolean
  onPrevious: () => void
  onNext: () => void
  onClose: () => void
  onFindSimilar: () => void
  onAddTag: (word: string) => void
  onAddCharacter: (word: string) => void
  onError: (text: string) => void
}) {
  const { hit } = props
  const [detail, setDetail] = useState<Detail | null>(null)
  const [path, setPath] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    setDetail(null)
    setPath(null)
    window.gallery.detail(hit.handle).then((d) => live && setDetail(d), () => {})
    window.gallery.path(hit.handle).then(
      (p) => live && setPath(p),
      () => live && setPath('(no longer in the drive)')
    )
    return () => {
      live = false
    }
  }, [hit.handle])

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLVideoElement) return
      if (e.key === 'Escape') props.onClose()
      else if (e.key === 'ArrowLeft' && props.hasPrevious) props.onPrevious()
      else if (e.key === 'ArrowRight' && props.hasNext) props.onNext()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [props])

  function appAction(action: (handle: string) => Promise<void>) {
    action(hit.handle).catch((e: Error) => props.onError(e.message))
  }

  const navButton =
    'absolute top-1/2 grid h-11 w-11 -translate-y-1/2 place-items-center rounded-full bg-black/45 text-white/85 hover:bg-black/70 hover:text-white'
  const tagged = detail && (detail.general.length > 0 || detail.characters.length > 0)

  return (
    <div className="fixed inset-0 z-50 flex bg-black/75 p-6 pt-12 backdrop-blur-sm" onMouseDown={props.onClose}>
      <div
        className="flex min-h-0 flex-1 overflow-hidden rounded-xl bg-neutral-900 shadow-2xl ring-1 ring-white/10"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="relative flex min-w-0 flex-1 items-center justify-center bg-black">
          {hit.video ? <VideoPlayer handle={hit.handle} /> : <PreviewImage hit={hit} />}
          {props.hasPrevious && (
            <button className={`${navButton} left-3`} onClick={props.onPrevious} title="Previous (←)">
              <ChevronLeft size={22} />
            </button>
          )}
          {props.hasNext && (
            <button className={`${navButton} right-3`} onClick={props.onNext} title="Next (→)">
              <ChevronRight size={22} />
            </button>
          )}
          <span className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded bg-black/55 px-2 py-0.5 text-xs text-white/75 tabular-nums">
            {props.position}
          </span>
        </div>

        <aside className="flex w-[360px] shrink-0 flex-col border-l border-white/5">
          <div className="flex items-start gap-2 px-5 pt-4 pb-3">
            <h2 className="selectable min-w-0 flex-1 text-base font-semibold break-all text-white">{hit.name}</h2>
            <button
              onClick={props.onClose}
              title="Close (Esc)"
              className="-mt-1 -mr-2 grid h-8 w-8 shrink-0 place-items-center rounded-md text-neutral-400 hover:bg-white/10 hover:text-white"
            >
              <X size={18} />
            </button>
          </div>

          <div className="flex flex-col gap-2 px-5 pb-4">
            <button
              onClick={props.onFindSimilar}
              disabled={!tagged}
              title={tagged ? undefined : 'This file has no WD Tagger tags'}
              className="flex h-9 items-center justify-center gap-2 rounded-md bg-violet-600 text-sm font-medium text-white hover:bg-violet-500 disabled:bg-neutral-700 disabled:text-neutral-400"
            >
              <Sparkles size={15} /> Find similar
            </button>
            <div className="flex gap-2">
              <button
                onClick={() => appAction(window.gallery.open)}
                className="flex h-8 flex-1 items-center justify-center gap-1.5 rounded-md bg-white/8 text-[13px] text-neutral-200 hover:bg-white/15"
              >
                <ExternalLink size={14} /> Open in app
              </button>
              <button
                onClick={() => appAction(window.gallery.reveal)}
                className="flex h-8 flex-1 items-center justify-center gap-1.5 rounded-md bg-white/8 text-[13px] text-neutral-200 hover:bg-white/15"
              >
                <FolderOpen size={14} /> Show in folder
              </button>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto border-t border-white/5 px-5 py-3">
            <dl>
              <Row label="Path">{path ?? <span className="text-neutral-500">…</span>}</Row>
              <Row label="Size">
                {formatSize(hit.size)} <span className="text-neutral-500">({hit.size.toLocaleString()} bytes)</span>
              </Row>
              <Row label="Modified">{formatDate(hit.mtime * 1000)}</Row>
              <Row label="Rating">
                {hit.rating ? (
                  <span className="inline-flex items-center gap-1.5">
                    <span className={`h-2 w-2 rounded-full ${RATING_COLOURS[hit.rating]}`} />
                    {RATING_LABELS[hit.rating]}
                  </span>
                ) : (
                  <span className="text-neutral-500">None</span>
                )}
              </Row>
              {hit.score !== undefined && <Row label="Similarity">{(hit.score * 100).toFixed(1)}%</Row>}
            </dl>

            {detail && detail.characters.length > 0 && (
              <section className="mt-4">
                <h3 className="mb-2 text-xs font-semibold tracking-wide text-neutral-400 uppercase">Characters</h3>
                <div className="flex flex-wrap gap-1.5">
                  {detail.characters.map((c) => (
                    <TagChip key={c} text={c} tone="character" onClick={() => props.onAddCharacter(c)} />
                  ))}
                </div>
              </section>
            )}

            {detail && detail.user.length > 0 && (
              <section className="mt-4">
                <h3 className="mb-2 text-xs font-semibold tracking-wide text-neutral-400 uppercase">Your tags</h3>
                <div className="flex flex-wrap gap-1.5">
                  {detail.user.map((t) => (
                    <TagChip key={t} text={t} tone="user" onClick={() => props.onAddTag(t)} />
                  ))}
                </div>
              </section>
            )}

            <section className="mt-4 mb-2">
              <h3 className="mb-2 text-xs font-semibold tracking-wide text-neutral-400 uppercase">
                Tags {detail && <span className="font-normal text-neutral-500">({detail.general.length})</span>}
              </h3>
              {detail && detail.general.length === 0 && <p className="text-[13px] text-neutral-500">Not tagged by WD Tagger.</p>}
              <div className="flex flex-wrap gap-1.5">
                {detail?.general.map((t) => <TagChip key={t} text={t} onClick={() => props.onAddTag(t)} />)}
              </div>
            </section>
          </div>
        </aside>
      </div>
    </div>
  )
}
