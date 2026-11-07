import { contextBridge, ipcRenderer } from 'electron'
import type { GalleryApi, IndexStatus } from '../shared/types'

const api: GalleryApi = {
  status: () => ipcRenderer.invoke('status'),
  onStatus: (listener) => {
    ipcRenderer.on('status', (_event, status: IndexStatus) => listener(status))
  },
  rebuild: () => ipcRenderer.send('rebuild'),
  search: (request) => ipcRenderer.invoke('search', request),
  suggest: (kind, text) => ipcRenderer.invoke('suggest', kind, text),
  detail: (handle) => ipcRenderer.invoke('detail', handle),
  path: (handle) => ipcRenderer.invoke('path', handle),
  streamUrl: (handle) => ipcRenderer.invoke('stream-url', handle),
  open: (handle) => ipcRenderer.invoke('open', handle),
  reveal: (handle) => ipcRenderer.invoke('reveal', handle)
}

contextBridge.exposeInMainWorld('gallery', api)
