// The slideshow window. State flows one way:
//   settings + items --buildPlaylist--> playlist; currentHandle picks the target in it;
//   the target is loaded (ImageLoader), then becomes the current Slide on the Stage;
//   once shown, the interval timer advances currentHandle.
// The current image is tracked by handle, not index, so re-sorting or filtering keeps it on
// screen when it survives the change.

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, FolderSearch, Maximize, Minimize, Pause, Play, Settings2 } from 'lucide-react'
import type { Session, Settings } from '@shared/types'
import { buildPlaylist, formatDate, formatSize, shortTag } from './playlist'
import { ImageLoader } from './loader'
import { Slide, Stage } from './Stage'
import { SettingsPanel } from './SettingsPanel'

const IDLE_MS = 2500
const TITLE_BAR = 36

function newSeed(): number {
  return Math.floor(Math.random() * 0xffffffff)
}

function IconButton(props: { title: string; onClick: () => void; children: React.ReactNode; active?: boolean }) {
  return (
    <button
      title={props.title}
      onClick={props.onClick}
      className={`grid h-9 w-9 place-items-center rounded-full transition-colors hover:bg-white/15 ${
        props.active ? 'bg-white/15 text-white' : 'text-white/80 hover:text-white'
      }`}
    >
      {props.children}
    </button>
  )
}

// Remounted (by key) whenever the advance timer restarts, so it always runs in step with it.
function CountdownBar(props: { durationMs: number }) {
  const ref = useRef<HTMLDivElement>(null)
  useLayoutEffect(() => {
    const animation = ref.current?.animate([{ transform: 'scaleX(1)' }, { transform: 'scaleX(0)' }], {
      duration: props.durationMs,
      easing: 'linear',
      fill: 'forwards'
    })
    return () => animation?.cancel()
  }, [props.durationMs])
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 z-30 h-1">
      <div ref={ref} className="h-full origin-left bg-red-600/70" />
    </div>
  )
}

export function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [settings, setSettings] = useState<Settings | null>(null)
  const [seed, setSeed] = useState(newSeed)
  const [currentHandle, setCurrentHandle] = useState<string | null>(null)
  const [slides, setSlides] = useState<{ current: Slide | null; leaving: Slide | null }>({ current: null, leaving: null })
  const [shownHandle, setShownHandle] = useState<string | null>(null)
  const [playing, setPlaying] = useState(true)
  const [loadingVisible, setLoadingVisible] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [active, setActive] = useState(true)
  const [hoveringControls, setHoveringControls] = useState(false)
  const [panelOpen, setPanelOpen] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)

  const loader = useMemo(() => new ImageLoader(), [])
  const slideKey = useRef(0)
  const direction = useRef<1 | -1>(1)
  const failures = useRef(0)

  useEffect(() => {
    window.slideshow.loadSession().then(
      (s) => {
        setSession(s)
        setSettings(s.settings)
      },
      (e: unknown) => setError(e instanceof Error ? e.message.replace(/^Error invoking remote method '[^']+': /, '') : String(e))
    )
  }, [])

  // Saved a moment after the last change, so dragging a slider writes the file once.
  useEffect(() => {
    if (!settings) return
    const t = window.setTimeout(() => window.slideshow.saveSettings(settings), 400)
    return () => window.clearTimeout(t)
  }, [settings])

  const playlist = useMemo(
    () =>
      session && settings
        ? buildPlaylist(session.items, settings.filters, settings.sortKey, settings.sortDescending, seed)
        : [],
    [session, settings?.filters, settings?.sortKey, settings?.sortDescending, seed]
  )
  const found = playlist.findIndex((item) => item.handle === currentHandle)
  const index = found < 0 ? 0 : found
  const target = playlist[index] ?? null

  const state = useRef({ playlist, index, settings })
  state.current = { playlist, index, settings }

  const showToast = useCallback((text: string) => setToast(text), [])
  useEffect(() => {
    if (!toast) return
    const t = window.setTimeout(() => setToast(null), 2500)
    return () => window.clearTimeout(t)
  }, [toast])

  // auto: moved by the timer, so "At the end" applies; a manual move past the end wraps.
  const advance = useCallback((step: 1 | -1, auto: boolean) => {
    const { playlist: list, index: i, settings: s } = state.current
    if (!list.length || !s) return
    let next = i + step
    if (next >= list.length) {
      if (auto && s.atEnd === 'stop') {
        setPlaying(false)
        return
      }
      if (auto && s.atEnd === 'close') {
        window.slideshow.close()
        return
      }
      if (s.sortKey === 'random') {
        // A new lap gets a new order; null makes the first image of it the target.
        direction.current = 1
        setSeed(newSeed())
        setCurrentHandle(null)
        return
      }
      next = 0
    }
    if (next < 0) next = list.length - 1
    direction.current = step
    setCurrentHandle(list[next].handle)
  }, [])

  // Load the target and put it on the stage.
  useEffect(() => {
    if (!target || target.handle === shownHandle) return
    let cancelled = false
    const spinner = window.setTimeout(() => setLoadingVisible(true), 400)
    loader.load(target).then(
      (image) => {
        if (cancelled) return
        failures.current = 0
        slideKey.current += 1
        setSlides((s) => ({ current: { key: slideKey.current, src: image.src, direction: direction.current }, leaving: s.current }))
        setShownHandle(target.handle)
      },
      () => {
        if (cancelled) return
        showToast(`Couldn't load ${target.name}`)
        failures.current += 1
        if (failures.current < state.current.playlist.length) advance(direction.current, false)
        else setPlaying(false)
      }
    )
    return () => {
      cancelled = true
      window.clearTimeout(spinner)
      setLoadingVisible(false)
    }
  }, [target, shownHandle, loader, advance, showToast])

  // Once the target is on screen: prefetch what follows it in the current order.
  useEffect(() => {
    if (!target || target.handle !== shownHandle) return
    loader.keepAround(playlist, index)
    loader.prefetch(playlist, index)
  }, [playlist, index, target, shownHandle, loader])

  useEffect(() => {
    if (!slides.leaving || !settings) return
    const t = window.setTimeout(() => setSlides((s) => ({ ...s, leaving: null })), settings.transitionMs)
    return () => window.clearTimeout(t)
  }, [slides.leaving, settings?.transitionMs])

  // The interval counts from when the image is shown, so a slow load never shortens it.
  useEffect(() => {
    if (!playing || !settings || !target || target.handle !== shownHandle) return
    const t = window.setTimeout(() => advance(1, true), settings.intervalSec * 1000)
    return () => window.clearTimeout(t)
  }, [playing, settings?.intervalSec, target, shownHandle, slides.current?.key, advance])

  const toggleFullscreen = useCallback(() => {
    if (document.fullscreenElement) void document.exitFullscreen()
    else void document.documentElement.requestFullscreen()
  }, [])
  useEffect(() => {
    const onChange = (): void => setFullscreen(document.fullscreenElement !== null)
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])

  const idleTimer = useRef(0)
  const wake = useCallback(() => {
    setActive(true)
    window.clearTimeout(idleTimer.current)
    idleTimer.current = window.setTimeout(() => setActive(false), IDLE_MS)
  }, [])
  useEffect(() => {
    wake()
    return () => window.clearTimeout(idleTimer.current)
  }, [wake])

  const changeInterval = useCallback(
    (delta: number) => {
      setSettings((s) => {
        if (!s) return s
        const intervalSec = Math.min(60, Math.max(1, s.intervalSec + delta))
        showToast(`${intervalSec.toFixed(1)} s per image`)
        return { ...s, intervalSec }
      })
    },
    [showToast]
  )

  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      const typing = e.target instanceof HTMLInputElement && e.target.type !== 'range'
      if (e.key === 'Escape') {
        if (panelOpen) setPanelOpen(false)
        else if (document.fullscreenElement) void document.exitFullscreen()
        return
      }
      if (typing) return
      switch (e.key) {
        case ' ':
          e.preventDefault()
          setPlaying((p) => !p)
          break
        case 'ArrowRight':
          e.preventDefault()
          advance(1, false)
          break
        case 'ArrowLeft':
          e.preventDefault()
          advance(-1, false)
          break
        case 'f':
        case 'F':
        case 'F11':
          e.preventDefault()
          toggleFullscreen()
          break
        case 's':
        case 'S':
          setPanelOpen((p) => !p)
          break
        case '+':
        case '=':
          changeInterval(0.5)
          break
        case '-':
          changeInterval(-0.5)
          break
        default:
          return
      }
      wake()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [panelOpen, advance, toggleFullscreen, changeInterval, wake])

  const lastWheel = useRef(0)
  const onWheel = (e: React.WheelEvent): void => {
    const now = performance.now()
    if (now - lastWheel.current < 250 || e.deltaY === 0) return
    lastWheel.current = now
    advance(e.deltaY > 0 ? 1 : -1, false)
  }

  const showChrome = active || hoveringControls || panelOpen
  const top = fullscreen ? 0 : TITLE_BAR
  const shown = playlist.find((item) => item.handle === shownHandle) ?? null

  return (
    <div className={`fixed inset-0 overflow-hidden bg-black text-white ${showChrome ? '' : 'cursor-none'}`} onMouseMove={wake}>
      {!fullscreen && (
        <div className="drag fixed inset-x-0 top-0 z-40 flex items-center pl-4 text-[12px] text-white/45" style={{ height: TITLE_BAR }}>
          <span className="truncate pr-40">{session ? session.scope : 'Slideshow'}</span>
        </div>
      )}

      <main className="absolute inset-x-0 bottom-0" style={{ top }} onWheel={onWheel}>
        {settings && (
          <Stage
            current={slides.current}
            leaving={slides.leaving}
            fit={settings.fit}
            transition={settings.transition}
            durationMs={settings.transitionMs}
          />
        )}

        {playlist.length > 1 && (
          <>
            <button className="edge group absolute inset-y-0 left-0 w-[16%]" onClick={() => advance(-1, false)} title="Previous (←)">
              <ChevronLeft className={`ml-4 opacity-0 transition-opacity ${showChrome ? 'group-hover:opacity-70' : ''}`} size={36} />
            </button>
            <button
              className="edge group absolute inset-y-0 right-0 flex w-[16%] justify-end"
              onClick={() => advance(1, false)}
              title="Next (→)"
            >
              <ChevronRight className={`mr-4 self-center opacity-0 transition-opacity ${showChrome ? 'group-hover:opacity-70' : ''}`} size={36} />
            </button>
          </>
        )}
        <div className="absolute inset-y-0 left-[16%] right-[16%]" onDoubleClick={toggleFullscreen} />

        {(loadingVisible || (!session && !error)) && (
          <div className="pointer-events-none absolute inset-0 grid place-items-center">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-white/15 border-t-white/70" />
          </div>
        )}

        {(error || (session && playlist.length === 0)) && (
          <div className="absolute inset-0 grid place-items-center">
            <div className="max-w-md space-y-3 text-center">
              <p className="text-[15px] text-white/80">
                {error
                  ? `Couldn't list the images: ${error}`
                  : session!.items.length === 0
                    ? `No images in ${session!.scope}.`
                    : 'No images match the filter.'}
              </p>
              {session && session.items.length > 0 && (
                <button className="rounded-full bg-white/12 px-4 py-1.5 text-[13px] hover:bg-white/20" onClick={() => setPanelOpen(true)}>
                  Open settings
                </button>
              )}
            </div>
          </div>
        )}

        {shown && (
          <div
            className={`pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/75 via-black/30 to-transparent px-6 pt-24 pb-5 transition-opacity duration-300 ${
              showChrome ? 'opacity-100' : 'opacity-0'
            }`}
          >
            <div className="max-w-[40%] space-y-1">
              <p className="truncate text-[14px] font-medium">{shown.name}</p>
              <p className="text-[12px] text-white/55 tabular-nums">
                {index + 1} / {playlist.length} · {formatDate(shown.mtime)} · {formatSize(shown.size)}
              </p>
              <p className="truncate text-[12px] text-white/40">{shown.path.slice(0, shown.path.lastIndexOf('/')) || '/'}</p>
              {shown.tags.length > 0 && (
                // One line, cut with an ellipsis: inline (not inline-block) chips, so text-overflow
                // applies to them and a single overlong tag is cut too.
                <p className="truncate pt-1 text-[11px] leading-5 text-white/70">
                  {shown.tags.map((tag) => (
                    <span key={tag} className="mr-1 rounded-full bg-white/10 px-2 py-px">
                      {shortTag(tag)}
                    </span>
                  ))}
                </p>
              )}
            </div>
          </div>
        )}

        {settings && session && playlist.length > 0 && (
          <div
            className={`absolute bottom-5 left-1/2 z-20 flex -translate-x-1/2 items-center gap-0.5 rounded-full border border-white/10 bg-neutral-900/60 p-1 shadow-xl backdrop-blur-xl transition-opacity duration-300 ${
              showChrome ? 'opacity-100' : 'pointer-events-none opacity-0'
            }`}
            onMouseEnter={() => setHoveringControls(true)}
            onMouseLeave={() => setHoveringControls(false)}
          >
            <IconButton title="Previous (←)" onClick={() => advance(-1, false)}>
              <ChevronLeft size={18} />
            </IconButton>
            <IconButton title={playing ? 'Pause (Space)' : 'Play (Space)'} onClick={() => setPlaying((p) => !p)}>
              {playing ? <Pause size={18} /> : <Play size={18} />}
            </IconButton>
            <IconButton title="Next (→)" onClick={() => advance(1, false)}>
              <ChevronRight size={18} />
            </IconButton>
            <span className="px-2 text-[12px] text-white/55 tabular-nums" title="Seconds per image (+ / −)">
              {settings.intervalSec.toFixed(1)} s
            </span>
            <div className="mx-1 h-5 w-px bg-white/10" />
            <IconButton title="Show in MEGA Explorer" onClick={() => shown && void window.slideshow.reveal(shown.handle)}>
              <FolderSearch size={17} />
            </IconButton>
            <IconButton title="Settings (S)" onClick={() => setPanelOpen((p) => !p)} active={panelOpen}>
              <Settings2 size={17} />
            </IconButton>
            <IconButton title={fullscreen ? 'Exit full screen (F11)' : 'Full screen (F11)'} onClick={toggleFullscreen}>
              {fullscreen ? <Minimize size={17} /> : <Maximize size={17} />}
            </IconButton>
          </div>
        )}

        {playing && !fullscreen && settings?.showCountdown && target && target.handle === shownHandle && (
          <CountdownBar key={`${slides.current?.key}:${settings.intervalSec}`} durationMs={settings.intervalSec * 1000} />
        )}

        {!playing && shown && !showChrome && (
          <div className="pointer-events-none absolute top-4 right-4 rounded-full bg-black/50 p-2 text-white/70">
            <Pause size={14} />
          </div>
        )}

        {toast && (
          <div className="pointer-events-none absolute bottom-20 left-1/2 z-30 -translate-x-1/2 rounded-full bg-neutral-900/80 px-4 py-1.5 text-[12px] text-white/85 shadow-lg backdrop-blur">
            {toast}
          </div>
        )}

        {panelOpen && settings && session && (
          <SettingsPanel
            settings={settings}
            items={session.items}
            matchCount={playlist.length}
            onChange={setSettings}
            onClose={() => setPanelOpen(false)}
          />
        )}
      </main>
    </div>
  )
}
