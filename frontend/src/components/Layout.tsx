import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { useTheme } from '@/context/ThemeContext'
import { useWebSocket } from '@/context/WebSocketContext'
import {
  LayoutDashboard, Globe, BriefcaseBusiness, Settings, LogOut, Sun, Moon, Wifi, WifiOff, Shield
} from 'lucide-react'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/domains', icon: Globe, label: 'Domains' },
  { to: '/jobs', icon: BriefcaseBusiness, label: 'Jobs' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const { isConnected } = useWebSocket()
  const navigate = useNavigate()

  const handleLogout = () => { logout(); navigate('/login') }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 bg-[hsl(var(--sidebar,var(--card)))] border-r border-[hsl(var(--sidebar-border,var(--border)))] flex flex-col">
        {/* Logo */}
        <div className="px-5 py-5 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
            <Shield size={16} className="text-primary-foreground" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight">Classifier</h1>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-2 space-y-0.5">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-md text-[13px] font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-primary/15 text-primary dark:text-[hsl(265,55%,70%)]'
                    : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
                }`
              }
            >
              <Icon size={16} strokeWidth={isConnected ? 1.5 : 1.5} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-3 py-3 border-t border-[hsl(var(--sidebar-border,var(--border)))]">
          <div className="flex items-center justify-between mb-2 px-2">
            <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              {isConnected
                ? <><Wifi size={12} className="text-emerald-500" /> <span className="text-emerald-500">Live</span></>
                : <><WifiOff size={12} className="text-red-400" /> <span className="text-red-400">Offline</span></>
              }
            </div>
            <button onClick={toggleTheme} className="p-1 rounded hover:bg-accent/50 text-muted-foreground hover:text-foreground transition-colors">
              {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
            </button>
          </div>

          <div className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-accent/30 transition-colors group">
            <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center text-[11px] font-bold text-primary">
              {user?.username?.[0]?.toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium truncate">{user?.username}</p>
              <p className="text-[10px] text-muted-foreground capitalize">{user?.role}</p>
            </div>
            <button onClick={handleLogout} className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-all">
              <LogOut size={13} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto bg-background">
        <div className="p-6 max-w-[1600px]">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
