export default function DashboardPage() {
    return (
        <main className="p-8">
            <h1 className="text-3xl font-bold mb-4">Voice AI Dashboard</h1>
            <p className="text-gray-400">
                Connect your microphone and start a session to interact with the AI agent.
            </p>
            {/* TODO: mount VoiceOrb, TranscriptFeed, MetricsPanel */}
        </main>
    );
}
