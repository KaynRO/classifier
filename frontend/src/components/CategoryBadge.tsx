import { cn } from '@/lib/utils'

function toTitleCase(str: string): string {
  return str
    .toLowerCase()
    .split(/[\s/]+/)
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

export default function CategoryBadge({ category, desired }: { category?: string | null; desired?: string | null }) {
  if (!category) return <span className="text-[11px] text-muted-foreground/50">--</span>

  const lower = category.toLowerCase()
  const display = toTitleCase(category)
  const isMatch = desired && lower.includes(desired.toLowerCase())

  let color = 'bg-secondary/80 text-secondary-foreground'
  // Risk / warning keywords FIRST — a "Suspicious" result must not fall
  // through to a generic grey pill because it happens to contain "business".
  if (lower.includes('malicious') || lower.includes('phishing') || lower.includes('malware') || lower.includes('spam') || lower.includes('fraud') || lower.includes('scam')) {
    color = 'bg-red-500/20 text-red-400 border border-red-500/30'
  } else if (lower.includes('suspicious') || lower.includes('high risk') || lower.includes('medium risk')) {
    color = 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
  } else if (lower.includes('uncategorized') || lower.includes('not found') || lower.includes('newly observed') || lower.includes('newly registered') || lower.includes('not rated')) {
    color = 'bg-orange-500/20 text-orange-400'
  } else if (lower.includes('business') || lower.includes('economy')) {
    color = 'bg-blue-500/15 text-blue-400'
  } else if (lower.includes('finance') || lower.includes('financial')) {
    color = 'bg-emerald-500/15 text-emerald-400'
  } else if (lower.includes('education')) {
    color = 'bg-purple-500/15 text-purple-400'
  } else if (lower.includes('health')) {
    color = 'bg-pink-500/15 text-pink-400'
  } else if (lower.includes('news') || lower.includes('media')) {
    color = 'bg-amber-500/15 text-amber-400'
  } else if (lower.includes('technology') || lower.includes('internet') || lower.includes('computer')) {
    color = 'bg-cyan-500/15 text-cyan-400'
  }

  return (
    <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium', color)}>
      {display}
      {desired && isMatch && <span className="text-emerald-400 ml-0.5">&#10003;</span>}
      {desired && !isMatch && !lower.includes('not found') && <span className="text-red-400 ml-0.5">&#10007;</span>}
    </span>
  )
}
