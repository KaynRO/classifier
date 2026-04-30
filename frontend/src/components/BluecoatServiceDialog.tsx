import { useState } from 'react'

// Verbatim from the #selFilteringService dropdown on
// https://sitereview.bluecoat.com/ (probed 2026-04-30, 20 options).
const BLUECOAT_SERVICES = [
  'Symantec Edge SWG',
  'Symantec Cloud SWG',
  'Symantec Unified Agent',
  'Symantec Endpoint Security',
  'Symantec Email Security.Cloud',
  'Symantec Messaging Gateway',
  'Symantec Web Isolation',
  'Symantec Browser Protection',
  'Symantec CacheFlow Appliance',
  'Symantec PacketShaper',
  'Symantec Security Analytics',
  'Symantec SSL Visibility',
  'Norton Safe Web',
  'Norton Core',
  'Norton Mobile',
  'Blue Coat ProxyClient',
  'Global Security One',
  'Zone Labs ZoneAlarm Pro',
  'ZyXEL ZyWall',
  'Other (please specify below)',
] as const

export default function BluecoatServiceDialog({
  context,
  onConfirm,
  onCancel,
}: {
  context: string
  onConfirm: (service: string) => void
  onCancel: () => void
}) {
  const [service, setService] = useState<string>('Symantec Edge SWG')
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-150" onClick={onCancel}>
      <div className="w-full max-w-sm bg-card rounded-xl border border-border p-6 shadow-2xl animate-in zoom-in-95 duration-150" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold mb-1">BlueCoat — Filtering Service</h3>
        <p className="text-xs text-muted-foreground mb-4">{context}</p>
        <label className="text-xs font-medium text-muted-foreground block mb-1.5">Service</label>
        <select
          value={service}
          onChange={e => setService(e.target.value)}
          className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-1 focus:ring-ring mb-5"
        >
          {BLUECOAT_SERVICES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <div className="flex justify-end gap-2">
          <button onClick={onCancel} className="px-4 py-2 rounded-md border border-border text-sm font-medium hover:bg-accent transition-colors">
            Cancel
          </button>
          <button onClick={() => onConfirm(service)} className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:brightness-110 transition-all">
            Submit
          </button>
        </div>
      </div>
    </div>
  )
}
