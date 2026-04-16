import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { vendorsApi, settingsApi } from '@/api/client'
import { useAuth } from '@/context/AuthContext'
import { useTheme } from '@/context/ThemeContext'
import { Sun, Moon, Shield, User, Key, Eye, EyeOff, Save, Loader2, ChevronDown, ChevronRight } from 'lucide-react'
import toast from 'react-hot-toast'

const CREDENTIAL_GROUPS = [
  {
    label: 'Reputation & Threat Intel',
    keys: [
      { key: 'virustotal_api_key',           label: 'VirusTotal API Key',            type: 'key'    as const },
      { key: 'abuseipdb_api_key',            label: 'AbuseIPDB API Key',             type: 'key'    as const },
      { key: 'urlhaus_api_key',              label: 'URLhaus (AbuseCH) API Key',     type: 'key'    as const },
      { key: 'google_safebrowsing_api_key',  label: 'Google Safe Browsing API Key',  type: 'key'    as const },
    ],
  },
  {
    label: 'Captcha Solvers',
    keys: [
      { key: 'twocaptcha_api_key',    label: '2Captcha API Key',          type: 'key'    as const },
      { key: 'capsolver_api_key',     label: 'CapSolver API Key',         type: 'key'    as const },
      { key: 'brightdata_api_key',    label: 'BrightData API Key',        type: 'key'    as const },
      { key: 'brightdata_browser_ws', label: 'BrightData Browser WS URL', type: 'text'   as const },
    ],
  },
  {
    label: 'CheckPoint UserCenter',
    keys: [
      { key: 'checkpoint_username',    label: 'Username',    type: 'text'   as const },
      { key: 'checkpoint_password',    label: 'Password',    type: 'secret' as const },
      { key: 'checkpoint_totp_secret', label: 'TOTP Secret', type: 'secret' as const },
    ],
  },
  {
    label: 'Vendor Credentials',
    keys: [
      { key: 'talos_username',      label: 'Talos Username',      type: 'text'   as const },
      { key: 'talos_password',      label: 'Talos Password',      type: 'secret' as const },
      { key: 'watchguard_username', label: 'WatchGuard Username', type: 'text'   as const },
      { key: 'watchguard_password', label: 'WatchGuard Password', type: 'secret' as const },
      { key: 'paloalto_username',   label: 'Palo Alto Username',  type: 'text'   as const },
      { key: 'paloalto_password',   label: 'Palo Alto Password',  type: 'secret' as const },
      { key: 'gmail_email',         label: 'Gmail Email',         type: 'text'   as const },
      { key: 'gmail_app_password',  label: 'Gmail App Password',  type: 'secret' as const },
    ],
  },
]

function CredentialField({
  fieldKey, label, type, serverValue, onChange,
}: {
  fieldKey: string
  label: string
  type: 'key' | 'text' | 'secret'
  serverValue: string
  onChange: (key: string, value: string) => void
}) {
  const [localValue, setLocalValue] = useState('')
  const [revealed, setRevealed] = useState(false)
  const hasStored = !!serverValue
  const inputType = (type === 'secret' || type === 'key') && !revealed ? 'password' : 'text'

  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-border/40 last:border-0">
      <div className="flex-1 min-w-0">
        <label className="block text-xs font-medium text-foreground/80 mb-1">{label}</label>
        <div className="flex items-center gap-1.5">
          <input
            type={inputType}
            value={localValue}
            placeholder={hasStored ? '(stored — enter new value to replace)' : 'Enter value…'}
            onChange={e => { setLocalValue(e.target.value); onChange(fieldKey, e.target.value) }}
            className="flex-1 min-w-0 px-3 py-1.5 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-1 focus:ring-ring font-mono placeholder:font-sans placeholder:text-muted-foreground/40"
          />
          {(type === 'secret' || type === 'key') && (
            <button
              type="button"
              onClick={() => setRevealed(r => !r)}
              className="p-1.5 rounded-md border border-border hover:bg-accent text-muted-foreground transition-colors flex-shrink-0"
              title={revealed ? 'Hide' : 'Show'}
            >
              {revealed ? <EyeOff size={13} /> : <Eye size={13} />}
            </button>
          )}
        </div>
        {hasStored && !localValue && (
          <p className="text-[10px] text-emerald-500/80 mt-0.5">Configured</p>
        )}
      </div>
    </div>
  )
}

function CredentialGroup({
  group, serverValues, onChange,
}: {
  group: typeof CREDENTIAL_GROUPS[0]
  serverValues: Record<string, string>
  onChange: (key: string, value: string) => void
}) {
  const [open, setOpen] = useState(false)
  const configured = group.keys.filter(k => !!serverValues[k.key]).length

  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-[hsl(var(--table-header,var(--secondary)))] hover:bg-accent/50 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          {open ? <ChevronDown size={14} className="text-muted-foreground" /> : <ChevronRight size={14} className="text-muted-foreground" />}
          <span className="text-sm font-medium">{group.label}</span>
        </div>
        <span className="text-[11px] text-muted-foreground">{configured}/{group.keys.length} configured</span>
      </button>
      {open && (
        <div className="px-4 py-1 bg-card">
          {group.keys.map(k => (
            <CredentialField
              key={k.key}
              fieldKey={k.key}
              label={k.label}
              type={k.type}
              serverValue={serverValues[k.key] ?? ''}
              onChange={onChange}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export default function SettingsPage() {
  const { user } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const queryClient = useQueryClient()
  const isAdmin = user?.role === 'admin'

  const { data: vendors } = useQuery({
    queryKey: ['vendors'],
    queryFn: () => vendorsApi.list().then(r => r.data),
  })

  const { data: serverCreds = {} } = useQuery({
    queryKey: ['credentials'],
    queryFn: () => settingsApi.getCredentials().then(r => r.data),
    enabled: isAdmin,
  })

  const [pendingChanges, setPendingChanges] = useState<Record<string, string>>({})
  const handleChange = (key: string, value: string) => setPendingChanges(prev => ({ ...prev, [key]: value }))
  const hasPending = Object.values(pendingChanges).some(v => v.trim() !== '')

  const saveMutation = useMutation({
    mutationFn: () => settingsApi.updateCredentials(pendingChanges),
    onSuccess: () => {
      toast.success('Credentials saved')
      setPendingChanges({})
      queryClient.invalidateQueries({ queryKey: ['credentials'] })
    },
    onError: () => toast.error('Failed to save credentials'),
  })

  return (
    <div className="space-y-8 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Settings</h2>
        <p className="text-muted-foreground mt-1">Configure dashboard preferences and API credentials</p>
      </div>

      {/* Appearance */}
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

      {/* Profile */}
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

      {/* API Credentials */}
      <div className="rounded-lg border border-border bg-card p-6">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold flex items-center gap-2"><Key size={18} /> API Credentials</h3>
          {isAdmin && (
            <button
              onClick={() => saveMutation.mutate()}
              disabled={!hasPending || saveMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:brightness-110 disabled:opacity-40 transition-all"
            >
              {saveMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
              Save Changes
            </button>
          )}
        </div>
        {isAdmin ? (
          <>
            <p className="text-xs text-muted-foreground mb-5">
              Values saved here override environment variables and are applied on the next vendor check — no restart required.
              Leave a field blank to clear it.
            </p>
            <div className="space-y-3">
              {CREDENTIAL_GROUPS.map(group => (
                <CredentialGroup
                  key={group.label}
                  group={group}
                  serverValues={serverCreds as Record<string, string>}
                  onChange={handleChange}
                />
              ))}
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground mt-2">Admin access required to manage credentials.</p>
        )}
      </div>

      {/* Vendor Registry */}
      <div className="rounded-lg border border-border bg-card p-6">
        <h3 className="font-semibold mb-4 flex items-center gap-2"><Shield size={18} /> Vendor Registry</h3>
        <div className="space-y-2">
          {vendors?.map((vendor: any) => (
            <div key={vendor.id} className="flex items-center justify-between py-2 border-b border-border last:border-0">
              <div>
                <p className="font-medium text-sm">{vendor.display_name}</p>
                <p className="text-xs text-muted-foreground">
                  {vendor.vendor_type} · Check: {vendor.supports_check ? 'Yes' : 'No'} · Submit: {vendor.supports_submit ? 'Yes' : 'No'}
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
