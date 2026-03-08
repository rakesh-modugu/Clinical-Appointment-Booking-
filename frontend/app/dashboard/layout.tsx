export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="flex min-h-screen bg-gray-950 text-white">
            {/* Sidebar */}
            <aside className="w-64 border-r border-gray-800 p-6 flex flex-col gap-4">
                <span className="text-xl font-semibold">🎙 VoiceAI</span>
                <nav className="flex flex-col gap-2 text-sm text-gray-400">
                    <a href="/dashboard" className="hover:text-white transition">Dashboard</a>
                    <a href="/sessions" className="hover:text-white transition">Sessions</a>
                </nav>
            </aside>
            {/* Main content */}
            <div className="flex-1 flex flex-col">
                <header className="h-14 border-b border-gray-800 flex items-center px-6 text-sm text-gray-400">
                    Real-Time Voice AI Agent
                </header>
                <main className="flex-1 p-6">{children}</main>
            </div>
        </div>
    );
}
