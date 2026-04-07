import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
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
      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <div className="px-5 py-3 border-b border-border bg-[hsl(var(--table-header,var(--secondary)))] flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Domain / Vendor Matrix</h3>
          <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
            <RefreshCw size={12} className={messages.length > 0 ? 'animate-spin text-primary' : ''} />
            Auto-refreshing
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="text-sm" style={{ minWidth: `${240 + (matrix?.items?.[0]?.results?.length || 10) * 170}px` }}>
            <thead>
              <tr className="border-b border-border text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="px-5 py-2.5 text-left font-medium w-[240px] sticky left-0 bg-card z-10">Domain</th>
                {matrix?.items?.[0]?.results?.map((cell: any) => (
                  <th key={cell.vendor_name} className="px-4 py-2.5 text-center font-medium w-[170px]">
                    {cell.vendor_display_name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrix?.items?.map((row: any) => (
                <tr key={row.domain.id} className="border-b border-border hover:bg-[hsl(var(--table-row-hover,var(--accent)))] transition-colors">
                  <td className="px-5 py-2.5 sticky left-0 bg-card z-10">
                    <Link to={`/domains/${row.domain.id}`} className="font-medium hover:underline text-primary/90 dark:text-[hsl(265,50%,72%)]">
                      {row.domain.domain}
                    </Link>
                    {row.domain.desired_category && (
                      <div className="mt-0.5">
                        <span className="px-1.5 py-px rounded text-[10px] font-medium bg-primary/10 text-primary/70 dark:text-[hsl(265,40%,65%)]">{row.domain.desired_category}</span>
                      </div>
                    )}
                  </td>
                  {row.results.map((cell: any) => (
                    <td key={cell.vendor_name} className="px-4 py-2.5 text-center">
                      {cell.status === 'running' ? (
                        <StatusBadge status="running" />
                      ) : cell.status === 'success' ? (
                        <CategoryBadge category={cell.category} desired={row.domain.desired_category} />
                      ) : (
                        <StatusBadge status={cell.status} />
                      )}
                      {cell.last_checked && cell.status !== 'running' && (
                        <div className="text-[9px] text-muted-foreground/50 mt-0.5">{new Date(cell.last_checked).toLocaleDateString()}</div>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
              {(!matrix?.items || matrix.items.length === 0) && (
                <tr>
                  <td colSpan={20} className="px-5 py-12 text-center text-muted-foreground text-sm">
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
