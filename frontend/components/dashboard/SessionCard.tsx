interface Props {
    id: string;
    status: "started" | "ended" | "error";
    duration?: number;    // seconds
    totalTokens?: number;
    createdAt: string;
}

const STATUS_COLORS = {
    started: "bg-indigo-500",
    ended: "bg-emerald-500",
    error: "bg-red-500",
};

export function SessionCard({ id, status, duration, totalTokens, createdAt }: Props) {
    return (
        <a
            href={`/sessions/${id}`}
            className="block bg-gray-900 border border-gray-800 rounded-xl p-5 hover:border-indigo-500 transition"
        >
            <div className="flex justify-between items-start mb-3">
                <span className="text-sm font-mono text-gray-400 truncate">{id}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full text-white ${STATUS_COLORS[status]}`}>
                    {status}
                </span>
            </div>
            <div className="flex gap-4 text-xs text-gray-500">
                {duration !== undefined && <span>⏱ {duration.toFixed(1)}s</span>}
                {totalTokens !== undefined && <span>🔤 {totalTokens} tokens</span>}
                <span>📅 {new Date(createdAt).toLocaleString()}</span>
            </div>
        </a>
    );
}
