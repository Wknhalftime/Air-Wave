/**
 * Convert a string to Title Case for display.
 * Capitalizes the first letter of each word.
 */
export function toTitleCase(str: string | null | undefined): string {
  if (str == null || str === '') return str ?? '';
  return str
    .trim()
    .split(/\s+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

/** Matches "Various Artist" or "Various Artists" (case-insensitive). */
const VARIOUS_ARTIST_REGEX = /^Various Artists?$/i;

/**
 * Check if a string is the special "Various Artist(s)" placeholder.
 */
export function isVariousArtist(str: string | null | undefined): boolean {
  if (str == null || str === '') return false;
  return VARIOUS_ARTIST_REGEX.test(str.trim());
}

/**
 * Format artist name(s) for display. Filters out "Various Artist" / "Various Artists"
 * and applies title case. For comma-separated lists, removes those entries.
 */
export function formatArtistForDisplay(str: string | null | undefined): string {
  if (str == null || str === '') return str ?? '';
  const parts = str.split(',').map((s) => s.trim()).filter((s) => s && !isVariousArtist(s));
  const joined = parts.join(', ');
  return toTitleCase(joined);
}
