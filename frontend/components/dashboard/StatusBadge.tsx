type Status = "idle" | "listening" | "thinking" | "speaking";

interface Props { status: Status; }

const CONFIG: Record<Status, { label: string; color: string; dot: string }> = {
    idle: { label: "Idle", color: "text-gray-400", dot: "bg-gray-500" },
    listening: { label: "Listening", color: "text-indigo-400", dot: "bg-indigo-500" },
    thinking: { label: "Thinking", color: "text-amber-400", dot: "bg-amber-500" },
    speaking: { label: "Speaking", color: "text-emerald-400", dot: "bg-emerald-500" },
};

export function StatusBadge({ status }: Props) {
    const { label, color, dot } = CONFIG[status];
    return (
        <div className={`flex items-center gap-2 text-sm font-medium ${color}`}>
            <span className={`w-2 h-2 rounded-full animate-pulse ${dot}`} />
            {label}
        </div>
    );
}
