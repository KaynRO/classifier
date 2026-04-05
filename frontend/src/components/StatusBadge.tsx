import { cn } from '@/lib/utils'

const statusStyles: Record<string, string> = {
  success: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/20',
  failed: 'bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/20',
  running: 'bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/20 animate-pulse',
  pending: 'bg-yellow-500/15 text-yellow-700 dark:text-yellow-400 border-yellow-500/20',
  completed: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/20',
  cancelled: 'bg-gray-500/15 text-gray-700 dark:text-gray-400 border-gray-500/20',
}

export default function StatusBadge({ status }: { status: string | null | undefined }) {
  if (!status) return <span className="text-xs text-muted-foreground">--</span>
  return (
    <span className={cn(
      'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border',
      statusStyles[status] || statusStyles.pending
    )}>
      {status}
    </span>
  )
}
