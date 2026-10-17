import { contextBridge, ipcRenderer } from 'electron'
import type { Settings, SlideshowApi } from '../shared/types'

const api: SlideshowApi = {
  loadSession: () => ipcRenderer.invoke('load-session'),
  streamUrl: (handle) => ipcRenderer.invoke('stream-url', handle),
  reveal: (handle) => ipcRenderer.invoke('reveal', handle),
  saveSettings: (settings: Settings) => ipcRenderer.send('save-settings', settings),
  close: () => ipcRenderer.send('close')
}

contextBridge.exposeInMainWorld('slideshow', api)
