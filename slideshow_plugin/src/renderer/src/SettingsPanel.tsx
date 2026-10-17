import { useMemo, useState } from 'react'
import { X } from 'lucide-react'
import { DEFAULT_SETTINGS, extensionOf, IMAGE_EXTENSIONS } from '@shared/types'
import type { AtEnd, Filters, Fit, Item, Settings, SortKey, Transition } from '@shared/types'
import { shortTag } from './playlist'

interface Props {
  settings: Settings
  items: Item[]
  matchCount: number
  onChange: (settings: Settings) => void
  onClose: () => void
}

function Section(props: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3 border-t border-white/8 px-5 py-4 first:border-t-0">
      <h3 className="text-[11px] font-semibold tracking-wider text-white/40 uppercase">{props.title}</h3>
      {props.children}
    </section>
  )
}

function Row(props: { label: string; value?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between text-[13px]">
        <span className="text-white/70">{props.label}</span>
        {props.value && <span className="text-white/90 tabular-nums">{props.value}</span>}
      </div>
      {props.children}
    </div>
  )
}

function Segmented<T extends string>(props: {
  value: T
  options: [T, string][]
  onChange: (value: T) => void
  disabled?: boolean
}) {
  return (
    <div className={`flex rounded-lg bg-white/6 p-0.5 ${props.disabled ? 'pointer-events-none opacity-40' : ''}`}>
      {props.options.map(([value, label]) => (
        <button
          key={value}
          onClick={() => props.onChange(value)}
          className={`flex-1 rounded-md px-2 py-1 text-[12px] transition-colors ${
            props.value === value ? 'bg-white/15 text-white shadow-sm' : 'text-white/55 hover:text-white/85'
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

function Slider(props: { value: number; min: number; max: number; step: number; onChange: (v: number) => void; disabled?: boolean }) {
  return (
    <input
      type="range"
      className="slider w-full"
      min={props.min}
      max={props.max}
      step={props.step}
      value={props.value}
      disabled={props.disabled}
      onChange={(e) => props.onChange(Number(e.target.value))}
    />
  )
}

function Switch(props: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <button
      role="switch"
      aria-checked={props.checked}
      onClick={() => props.onChange(!props.checked)}
      className="flex w-full items-center justify-between text-[13px]"
    >
      <span className="text-white/70">{props.label}</span>
      <span className={`flex h-5 w-9 items-center rounded-full p-0.5 transition-colors ${props.checked ? 'bg-sky-500' : 'bg-white/15'}`}>
        <span className={`h-4 w-4 rounded-full bg-white shadow transition-transform ${props.checked ? 'translate-x-4' : ''}`} />
      </span>
    </button>
  )
}

const inputClass =
  'w-full rounded-lg border border-white/8 bg-white/6 px-2.5 py-1.5 text-[13px] text-white placeholder:text-white/30 outline-none focus:border-white/25'

function numberOrNull(text: string): number | null {
  const n = Number(text)
  return text.trim() === '' || !Number.isFinite(n) || n < 0 ? null : n
}

// A term is committed with Enter and then shown as a chip under the field; × removes it.
function TermChips(props: { value: string[]; placeholder: string; onChange: (terms: string[]) => void }) {
  const [draft, setDraft] = useState('')
  const commit = (): void => {
    const term = draft.trim()
    setDraft('')
    if (term && !props.value.some((t) => t.toLowerCase() === term.toLowerCase())) props.onChange([...props.value, term])
  }
  return (
    <div className="space-y-2">
      <input
        className={inputClass}
        placeholder={props.placeholder}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') commit()
        }}
      />
      {props.value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {props.value.map((term) => (
            <span key={term} title={term} className="flex items-center gap-1 rounded-full bg-white/12 py-0.5 pr-1 pl-2.5 text-[12px] text-white/85">
              {shortTag(term)}
              <button
                className="rounded-full p-0.5 text-white/50 hover:bg-white/15 hover:text-white"
                title="Remove"
                onClick={() => props.onChange(props.value.filter((t) => t !== term))}
              >
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export function SettingsPanel({ settings, items, matchCount, onChange, onClose }: Props) {
  const set = (patch: Partial<Settings>): void => onChange({ ...settings, ...patch })
  const f = settings.filters
  const setFilter = (patch: Partial<Filters>): void => set({ filters: { ...f, ...patch } })
  const present = useMemo(() => {
    const found = new Set(items.map((i) => extensionOf(i.name)))
    // jpeg counts as jpg, so the chips don't show the same format twice.
    return IMAGE_EXTENSIONS.filter((e) => e !== 'jpeg' && (found.has(e) || (e === 'jpg' && found.has('jpeg'))))
  }, [items])
  const toggleExtension = (ext: string): void => {
    const group = ext === 'jpg' ? ['jpg', 'jpeg'] : [ext]
    const off = f.extensionsExcluded.includes(ext)
    setFilter({
      extensionsExcluded: off ? f.extensionsExcluded.filter((e) => !group.includes(e)) : [...f.extensionsExcluded, ...group]
    })
  }
  const filtering = JSON.stringify(f) !== JSON.stringify(DEFAULT_SETTINGS.filters)

  return (
    <aside
      className="absolute top-0 right-0 bottom-0 z-30 flex w-[340px] flex-col border-l border-white/8 bg-neutral-950/80 shadow-2xl backdrop-blur-xl"
      onMouseDown={(e) => e.stopPropagation()}
      onDoubleClick={(e) => e.stopPropagation()}
      onWheel={(e) => e.stopPropagation()}
    >
      <header className="flex h-12 shrink-0 items-center justify-between px-5">
        <h2 className="text-[14px] font-medium text-white">Settings</h2>
        <button onClick={onClose} className="rounded-md p-1 text-white/50 hover:bg-white/10 hover:text-white" title="Close (Esc)">
          <X size={16} />
        </button>
      </header>
      <div className="flex-1 overflow-y-auto pb-6">
        <Section title="Playback">
          <Row label="Show each image for" value={`${settings.intervalSec.toFixed(1)} s`}>
            <Slider value={settings.intervalSec} min={1} max={60} step={0.5} onChange={(v) => set({ intervalSec: v })} />
          </Row>
          <Row label="Transition">
            <Segmented<Transition>
              value={settings.transition}
              options={[
                ['none', 'None'],
                ['fade', 'Fade'],
                ['slide', 'Slide'],
                ['zoom', 'Zoom']
              ]}
              onChange={(v) => set({ transition: v })}
            />
          </Row>
          <Row label="Transition length" value={settings.transition === 'none' ? '—' : `${(settings.transitionMs / 1000).toFixed(1)} s`}>
            <Slider
              value={settings.transitionMs}
              min={200}
              max={2000}
              step={100}
              disabled={settings.transition === 'none'}
              onChange={(v) => set({ transitionMs: v })}
            />
          </Row>
          <Row label="Image size">
            <Segmented<Fit>
              value={settings.fit}
              options={[
                ['contain', 'Fit'],
                ['cover', 'Fill'],
                ['actual', 'Actual size']
              ]}
              onChange={(v) => set({ fit: v })}
            />
          </Row>
          <Row label="At the end">
            <Segmented<AtEnd>
              value={settings.atEnd}
              options={[
                ['loop', 'Start over'],
                ['stop', 'Stop'],
                ['close', 'Close']
              ]}
              onChange={(v) => set({ atEnd: v })}
            />
          </Row>
        </Section>

        <Section title="Order">
          <Segmented<SortKey>
            value={settings.sortKey}
            options={[
              ['name', 'Name'],
              ['mtime', 'Date'],
              ['size', 'Size'],
              ['path', 'Path'],
              ['random', 'Random']
            ]}
            onChange={(v) => set({ sortKey: v })}
          />
          <Segmented<'asc' | 'desc'>
            value={settings.sortDescending ? 'desc' : 'asc'}
            options={[
              ['asc', 'Ascending'],
              ['desc', 'Descending']
            ]}
            disabled={settings.sortKey === 'random'}
            onChange={(v) => set({ sortDescending: v === 'desc' })}
          />
        </Section>

        <Section title="Filter">
          <p className="text-[12px] text-white/50">
            <span className="text-white/90 tabular-nums">{matchCount}</span> of{' '}
            <span className="tabular-nums">{items.length}</span> images
            {filtering && (
              <button onClick={() => setFilter(DEFAULT_SETTINGS.filters)} className="ml-2 text-sky-400 hover:text-sky-300">
                Clear filters
              </button>
            )}
          </p>
          <Row label="Name contains">
            <input className={inputClass} value={f.nameContains} onChange={(e) => setFilter({ nameContains: e.target.value })} />
          </Row>
          {present.length > 1 && (
            <Row label="Formats">
              <div className="flex flex-wrap gap-1.5">
                {present.map((ext) => {
                  const on = !f.extensionsExcluded.includes(ext)
                  return (
                    <button
                      key={ext}
                      onClick={() => toggleExtension(ext)}
                      className={`rounded-full px-2.5 py-0.5 text-[12px] uppercase transition-colors ${
                        on ? 'bg-white/15 text-white' : 'bg-white/5 text-white/35 line-through'
                      }`}
                    >
                      {ext}
                    </button>
                  )
                })}
              </div>
            </Row>
          )}
          <Switch label="Favourites only" checked={f.favouritesOnly} onChange={(v) => setFilter({ favouritesOnly: v })} />
          <Row label="Tags contain">
            <TermChips value={f.tagsInclude} placeholder="Type and press Enter" onChange={(v) => setFilter({ tagsInclude: v })} />
          </Row>
          <Row label="Tags don't contain">
            <TermChips value={f.tagsExclude} placeholder="Type and press Enter" onChange={(v) => setFilter({ tagsExclude: v })} />
          </Row>
          <Row label="Modified">
            <div className="flex items-center gap-2">
              <input type="date" className={inputClass} value={f.modifiedFrom} onChange={(e) => setFilter({ modifiedFrom: e.target.value })} />
              <span className="text-white/30">–</span>
              <input type="date" className={inputClass} value={f.modifiedTo} onChange={(e) => setFilter({ modifiedTo: e.target.value })} />
            </div>
          </Row>
          <Row label="Size (MB)">
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={0}
                step="0.1"
                placeholder="Min"
                className={inputClass}
                value={f.minSizeMB ?? ''}
                onChange={(e) => setFilter({ minSizeMB: numberOrNull(e.target.value) })}
              />
              <span className="text-white/30">–</span>
              <input
                type="number"
                min={0}
                step="0.1"
                placeholder="Max"
                className={inputClass}
                value={f.maxSizeMB ?? ''}
                onChange={(e) => setFilter({ maxSizeMB: numberOrNull(e.target.value) })}
              />
            </div>
          </Row>
        </Section>

        <Section title="Other">
          <Switch label="Countdown bar" checked={settings.showCountdown} onChange={(v) => set({ showCountdown: v })} />
        </Section>
      </div>
    </aside>
  )
}
