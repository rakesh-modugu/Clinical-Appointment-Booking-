"use client";
import { useEffect, useRef } from "react";

interface Turn {
    role: "user" | "assistant";
    content: string;
    timestamp: string;
}

interface Props {
    turns: Turn[];
}

/** Live-scrolling transcript feed showing user and assistant turns. */
export function TranscriptFeed({ turns }: Props) {
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [turns]);

    return (
        <div className="flex flex-col gap-3 h-96 overflow-y-auto pr-2">
            {turns.map((turn, i) => (
                <div
                    key={i}
                    className={`flex flex-col gap-1 ${turn.role === "user" ? "items-end" : "items-start"
                        }`}
                >
                    <span className="text-xs text-gray-500 capitalize">{turn.role}</span>
                    <div
                        className={`max-w-xs px-4 py-2 rounded-2xl text-sm ${turn.role === "user"
                                ? "bg-indigo-600 text-white"
                                : "bg-gray-800 text-gray-100"
                            }`}
                    >
                        {turn.content}
                    </div>
                </div>
            ))}
            <div ref={bottomRef} />
        </div>
    );
}
