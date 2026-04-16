import { cn } from '@/lib/utils'

function toTitleCase(str: string): string {
  return str
    .toLowerCase()
    .split(/[\s/]+/)
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

const RED_KEYWORDS = ['malicious', 'phishing', 'malware', 'spam', 'fraud', 'scam', 'botnet', 'ransomware', 'trojan', 'command and control']
const ORANGE_KEYWORDS = ['suspicious', 'high risk', 'medium risk', 'potentially unwanted', 'questionable']
const GREY_KEYWORDS = ['not found', 'not rated', 'uncategorized', 'unrated', 'none', 'unknown', 'newly observed', 'newly registered', 'parked', 'pending']

export default function CategoryBadge({ category, desired }: { category?: string | null; desired?: string | null }) {
  if (!category) return <span className="text-[11px] text-muted-foreground/50">--</span>

  const lower = category.toLowerCase()
  const display = toTitleCase(category)
  const isMatch = desired && lower.includes(desired.toLowerCase())

  let color: string
  if (RED_KEYWORDS.some(k => lower.includes(k))) {
    color = 'bg-red-500/20 text-red-400 border border-red-500/30'
  } else if (ORANGE_KEYWORDS.some(k => lower.includes(k))) {
    color = 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
  } else if (GREY_KEYWORDS.some(k => lower.includes(k))) {
    color = 'bg-secondary/60 text-muted-foreground'
  } else {
    color = 'bg-emerald-500/15 text-emerald-400'
  }

  return (
    <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium', color)}>
      {display}
      {desired && isMatch && <span className="text-emerald-400 ml-0.5">&#10003;</span>}
      {desired && !isMatch && !GREY_KEYWORDS.some(k => lower.includes(k)) && <span className="text-red-400 ml-0.5">&#10007;</span>}
    </span>
  )
}
