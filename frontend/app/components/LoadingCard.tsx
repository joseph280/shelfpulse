"use client";

import { useEffect, useState } from "react";

export function LoadingCard() {
    const [elapsed, setElapsed] = useState(0);

    useEffect(() => {
        const start = Date.now();
        const interval = setInterval(() => {
            setElapsed(Math.floor((Date.now() - start) / 1000));
        }, 1000);
        return () => clearInterval(interval);
    }, []);

    const stage = 
        elapsed < 5 ? "Routing your question..." :
        elapsed < 15 ? "Planning tool calls..." :
        elapsed < 30 ? "Querying the warehouse..." :
        elapsed < 50 ? "Drafting the insight..." :
        "Building the action plan...";

    return (
        <div className="flex justify-start mb-4">
        <div className="max-w-[80%] bg-agent-card border border-default rounded-2xl rounded-tl-md px-5 py-4 shadow-sm">
            <div className="flex items-center gap-3">
            <div className="flex gap-1">
                <span className="w-2 h-2 bg-accent rounded-full animate-pulse-subtle" />
                <span className="w-2 h-2 bg-accent rounded-full animate-pulse-subtle [animation-delay:200ms]" />
                <span className="w-2 h-2 bg-accent rounded-full animate-pulse-subtle [animation-delay:400ms]" />
            </div>
            <p className="text-sm text-muted">{stage}</p>
            <span className="text-xs text-muted ml-auto">{elapsed}s</span>
            </div>
        </div>
        </div>
    );
}