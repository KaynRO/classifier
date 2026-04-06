import { cn } from '@/lib/utils'
import { Loader2 } from 'lucide-react'

const styles: Record<string, string> = {
  clean: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  success: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  completed: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  failed: 'bg-red-500/20 text-red-400 border-red-500/30',
  error: 'bg-red-500/20 text-red-400 border-red-500/30',
  running: 'bg-sky-500/20 text-sky-400 border-sky-500/30',
  pending: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  submitted: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  uncategorized: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  cancelled: 'bg-neutral-500/20 text-neutral-400 border-neutral-500/30',
}

const labels: Record<string, string> = {
  success: 'clean',
  completed: 'completed',
}

export default function StatusBadge({ status, loading }: { status: string | null | undefined; loading?: boolean }) {
  if (loading) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-sky-500/20 text-sky-400 border border-sky-500/30">
        <Loader2 size={10} className="animate-spin" />
        checking
      </span>
    )
  }
  if (!status) return <span className="text-[11px] text-muted-foreground/50">--</span>
  const label = labels[status] || status
  return (
    <span className={cn(
      'inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border',
      styles[status] || styles.pending
    )}>
      {status === 'running' && <Loader2 size={10} className="animate-spin mr-1" />}
      {label}
    </span>
  )
}
