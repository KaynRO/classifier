import { useQuery } from '@tanstack/react-query'
import { vendorsApi } from '@/api/client'
import { useAuth } from '@/context/AuthContext'
import { useTheme } from '@/context/ThemeContext'
import { Sun, Moon, Shield, User } from 'lucide-react'

export default function SettingsPage() {
  const { user } = useAuth()
  const { theme, toggleTheme } = useTheme()

  const { data: vendors } = useQuery({
    queryKey: ['vendors'],
    queryFn: () => vendorsApi.list().then(r => r.data),
  })

  return (
    <div className="space-y-8 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Settings</h2>
        <p className="text-muted-foreground mt-1">Configure your dashboard preferences</p>
      </div>

      {/* Theme */}
      <div className="rounded-lg border border-border bg-card p-6">
        <h3 className="font-semibold mb-4">Appearance</h3>
        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium text-sm">Theme</p>
            <p className="text-xs text-muted-foreground mt-0.5">Toggle between light and dark mode</p>
          </div>
          <button
            onClick={toggleTheme}
            className="flex items-center gap-2 px-4 py-2 rounded-md border border-border text-sm hover:bg-accent transition-colors"
          >
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
          </button>
        </div>
      </div>

      {/* User Profile */}
      <div className="rounded-lg border border-border bg-card p-6">
        <h3 className="font-semibold mb-4 flex items-center gap-2"><User size={18} /> Profile</h3>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-muted-foreground">Username</p>
            <p className="font-medium mt-1">{user?.username}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Email</p>
            <p className="font-medium mt-1">{user?.email}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Role</p>
            <p className="font-medium mt-1 capitalize">{user?.role}</p>
          </div>
        </div>
      </div>

      {/* Vendors */}
      <div className="rounded-lg border border-border bg-card p-6">
        <h3 className="font-semibold mb-4 flex items-center gap-2"><Shield size={18} /> Vendor Registry</h3>
        <div className="space-y-2">
          {vendors?.map((vendor: any) => (
            <div key={vendor.id} className="flex items-center justify-between py-2 border-b border-border last:border-0">
              <div>
                <p className="font-medium text-sm">{vendor.display_name}</p>
                <p className="text-xs text-muted-foreground">
                  {vendor.vendor_type} | Check: {vendor.supports_check ? 'Yes' : 'No'} | Submit: {vendor.supports_submit ? 'Yes' : 'No'}
                </p>
              </div>
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${vendor.is_active ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400' : 'bg-red-500/15 text-red-700'}`}>
                {vendor.is_active ? 'Active' : 'Disabled'}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
