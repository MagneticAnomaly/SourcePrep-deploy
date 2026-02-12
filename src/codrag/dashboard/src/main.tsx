import React from 'react'
import ReactDOM from 'react-dom/client'
import { ApiClientProvider, CodragApiClient } from '@codrag/ui'
import { invoke } from '@tauri-apps/api/tauri'
import App from './App'
import './index.css'

const init = async () => {
  let baseUrl = window.location.origin;

  // Detect Tauri environment
  // @ts-ignore
  if (window.__TAURI__) {
    try {
      const config = await invoke<{ url: string }>('get_daemon_config');
      console.log('[Tauri] Daemon config:', config);
      baseUrl = config.url;
    } catch (e) {
      console.error('[Tauri] Failed to get daemon config:', e);
    }
  }

  const apiClient = new CodragApiClient({
    baseUrl,
  })

  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <ApiClientProvider client={apiClient}>
        <App />
      </ApiClientProvider>
    </React.StrictMode>,
  )
}

init();
