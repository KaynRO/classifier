export const CATEGORIES = ['Business', 'Education', 'Finance', 'Health', 'News', 'Internet'] as const
export type Category = typeof CATEGORIES[number]

export const HIDDEN_VENDORS = new Set(['lightspeedsystems'])
