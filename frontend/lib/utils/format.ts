/** Format a duration in seconds to a human-readable string, e.g. "1m 23s". */
export function formatDuration(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

/** Format an ISO date string to a short locale string. */
export function formatDate(iso: string): string {
    return new Date(iso).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

/** Format a token count with K suffix above 1000. */
export function formatTokens(count: number): string {
    return count >= 1000 ? `${(count / 1000).toFixed(1)}k` : String(count);
}
