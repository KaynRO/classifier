import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '@/context/AuthContext'
import { ThemeProvider } from '@/context/ThemeContext'
import { WebSocketProvider } from '@/context/WebSocketContext'
import { Toaster } from 'react-hot-toast'
import App from './App'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30000, retry: 1 },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <AuthProvider>
            <WebSocketProvider>
              <App />
              <Toaster
                position="bottom-right"
                toastOptions={{
                  className: '!bg-card !text-foreground !border !border-border !shadow-lg !text-sm',
                  duration: 4000,
                  success: { className: '!bg-card !text-emerald-500 !border !border-emerald-500/20 !shadow-lg !text-sm' },
                  error: { className: '!bg-card !text-red-500 !border !border-red-500/20 !shadow-lg !text-sm' },
                }}
              />
            </WebSocketProvider>
          </AuthProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </BrowserRouter>
  </React.StrictMode>
)
