// Dynamic route: /sessions/[id] — shows transcript and playback for one session
interface Props {
    params: { id: string };
}

export default function SessionDetailPage({ params }: Props) {
    return (
        <main className="p-8">
            <h1 className="text-2xl font-bold mb-4">Session {params.id}</h1>
            {/* TODO: fetch session data and render TranscriptFeed + AudioVisualizer */}
            <p className="text-gray-400">Loading session transcript...</p>
        </main>
    );
}
