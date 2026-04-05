import { useQuery } from '@tanstack/react-query'
import { dashboardApi, jobsApi } from '@/api/client'
import { useWebSocket } from '@/context/WebSocketContext'
import StatusBadge from '@/components/StatusBadge'
import CategoryBadge from '@/components/CategoryBadge'
import { Globe, Shield, AlertTriangle, Clock, RefreshCw } from 'lucide-react'

export default function DashboardPage() {
  const { data: summary } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: () => dashboardApi.summary().then(r => r.data),
    refetchInterval: 10000,
  })

  const { data: matrix } = useQuery({
    queryKey: ['dashboard-matrix'],
    queryFn: () => dashboardApi.matrix().then(r => r.data),
    refetchInterval: 15000,
  })

  const { messages } = useWebSocket()

  const stats = [
    { label: 'Active Domains', value: summary?.active_domains ?? '--', icon: Globe, color: 'text-blue-500' },
    { label: 'Total Vendors', value: summary?.total_vendors ?? '--', icon: Shield, color: 'text-emerald-500' },
    { label: 'Mismatches', value: summary?.domains_with_mismatches ?? '--', icon: AlertTriangle, color: 'text-amber-500' },
    { label: 'Pending Jobs', value: summary?.pending_jobs ?? '--', icon: Clock, color: 'text-purple-500' },
  ]

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
        <p className="text-muted-foreground mt-1">Overview of your domain classifications</p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="rounded-lg border border-border bg-card p-6">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">{label}</p>
              <Icon size={20} className={color} />
            </div>
            <p className="text-3xl font-bold mt-2">{value}</p>
          </div>
        ))}
      </div>

      {/* Domain Vendor Matrix */}
      <div className="rounded-lg border border-border bg-card">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h3 className="font-semibold">Domain / Vendor Matrix</h3>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <RefreshCw size={14} className={messages.length > 0 ? 'animate-spin text-blue-500' : ''} />
            Auto-refreshing
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="px-4 py-3 text-left font-medium text-muted-foreground sticky left-0 bg-card z-10">Domain</th>
                {matrix?.items?.[0]?.results?.map((cell: any) => (
                  <th key={cell.vendor_name} className="px-3 py-3 text-center font-medium text-muted-foreground whitespace-nowrap text-xs">
                    {cell.vendor_display_name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrix?.items?.map((row: any) => (
                <tr key={row.domain.id} className="border-b border-border hover:bg-accent/50 transition-colors">
                  <td className="px-4 py-3 font-medium sticky left-0 bg-card z-10">
                    <a href={`/domains/${row.domain.id}`} className="hover:underline">
                      {row.domain.domain}
                    </a>
                    {row.domain.desired_category && (
                      <span className="ml-2 text-xs text-muted-foreground">({row.domain.desired_category})</span>
                    )}
                  </td>
                  {row.results.map((cell: any) => (
                    <td key={cell.vendor_name} className="px-3 py-3 text-center">
                      {cell.status === 'success' ? (
                        <CategoryBadge category={cell.category} desired={row.domain.desired_category} />
                      ) : (
                        <StatusBadge status={cell.status} />
                      )}
                    </td>
                  ))}
                </tr>
              ))}
              {(!matrix?.items || matrix.items.length === 0) && (
                <tr>
                  <td colSpan={20} className="px-4 py-12 text-center text-muted-foreground">
                    No domains added yet. Go to Domains to add your first domain.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recent Activity */}
      {messages.length > 0 && (
        <div className="rounded-lg border border-border bg-card">
          <div className="p-4 border-b border-border">
            <h3 className="font-semibold">Live Activity</h3>
          </div>
          <div className="divide-y divide-border max-h-64 overflow-y-auto">
            {messages.slice(0, 10).map((msg, i) => (
              <div key={i} className="px-4 py-3 flex items-center justify-between text-sm">
                <div className="flex items-center gap-3">
                  <StatusBadge status={msg.status} />
                  <span className="font-medium">{msg.vendor}</span>
                  {msg.category && <CategoryBadge category={msg.category} />}
                </div>
                <span className="text-xs text-muted-foreground">
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
