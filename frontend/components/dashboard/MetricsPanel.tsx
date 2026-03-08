interface Metric {
    label: string;
    value: string | number;
    unit?: string;
}

interface Props {
    latencyMs?: number;
    totalTokens?: number;
    sessionDuration?: number;
}

export function MetricsPanel({ latencyMs, totalTokens, sessionDuration }: Props) {
    const metrics: Metric[] = [
        { label: "Latency", value: latencyMs ?? "—", unit: "ms" },
        { label: "Tokens", value: totalTokens ?? "—" },
        { label: "Duration", value: sessionDuration?.toFixed(1) ?? "—", unit: "s" },
    ];

    return (
        <div className="grid grid-cols-3 gap-4">
            {metrics.map((m) => (
                <div key={m.label} className="bg-gray-900 rounded-xl p-4 border border-gray-800">
                    <p className="text-xs text-gray-500 mb-1">{m.label}</p>
                    <p className="text-2xl font-semibold text-white">
                        {m.value}
                        {m.unit && <span className="text-sm text-gray-400 ml-1">{m.unit}</span>}
                    </p>
                </div>
            ))}
        </div>
    );
}
