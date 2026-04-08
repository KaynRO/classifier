export const CATEGORIES = ['Business', 'Education', 'Finance', 'Health', 'News', 'Internet'] as const
export type Category = typeof CATEGORIES[number]

export const HIDDEN_VENDORS = new Set(['lightspeedsystems'])

/**
 * Per-vendor manual check/submit URLs. Used when an automated task has
 * failed and the user wants to open the vendor's site and do it by hand.
 * Supports `{domain}` placeholder.
 */
export const VENDOR_MANUAL_URLS: Record<string, { check?: string; submit?: string }> = {
  // Category vendors
  bluecoat: { check: 'https://sitereview.bluecoat.com/#/', submit: 'https://sitereview.bluecoat.com/#/' },
  brightcloud: { check: 'https://www.brightcloud.com/tools/url-ip-lookup.php', submit: 'https://www.brightcloud.com/tools/change-request-url.php' },
  checkpoint: { check: 'https://usercenter.checkpoint.com/ucapps/urlcat/' },
  fortiguard: { check: 'https://www.fortiguard.com/webfilter', submit: 'https://www.fortiguard.com/faq/wfratingsubmit' },
  intelixsophos: { check: 'https://intelix.sophos.com/url', submit: 'https://support.sophos.com/support/s/filesubmission' },
  lightspeedsystems: { check: 'https://archive.lightspeedsystems.com/' },
  mcafee: { check: 'https://sitelookup.mcafee.com/', submit: 'https://sitelookup.mcafee.com/en/feedback/url' },
  paloalto: { check: 'https://urlfiltering.paloaltonetworks.com/', submit: 'https://urlfiltering.paloaltonetworks.com/' },
  talosintelligence: { check: 'https://talosintelligence.com/reputation_center/', submit: 'https://talosintelligence.com/reputation_center/support' },
  trendmicro: { check: 'https://global.sitesafety.trendmicro.com', submit: 'https://global.sitesafety.trendmicro.com' },
  watchguard: { check: 'https://securityportal.watchguard.com/UrlCategory', submit: 'https://securityportal.watchguard.com/UrlCategory' },
  zvelo: { check: 'https://tools.zvelo.com/', submit: 'https://tools.zvelo.com/' },
  // Reputation vendors — direct domain lookup pages
  virustotal: { check: 'https://www.virustotal.com/gui/domain/{domain}' },
  abuseipdb: { check: 'https://www.abuseipdb.com/check/{domain}' },
  abusech: { check: 'https://urlhaus.abuse.ch/browse.php?search={domain}' },
  googlesafebrowsing: { check: 'https://transparencyreport.google.com/safe-browsing/search?url={domain}' },
}

export function getManualUrl(vendorName: string, action: 'check' | 'submit', domain: string): string | null {
  const entry = VENDOR_MANUAL_URLS[vendorName]
  if (!entry) return null
  const url = entry[action] || entry.check || entry.submit
  if (!url) return null
  return url.replace('{domain}', encodeURIComponent(domain))
}
