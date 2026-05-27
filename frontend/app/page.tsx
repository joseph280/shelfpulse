"use client";

import { useState } from "react";
import { askShelfPulse, ApiError } from "@/lib/api";
import { ChatMessage, ChatThread } from "./components/ChatThread";
import { ChatInput } from "./components/ChatInput";


export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);

  function newId() {
    return Math.random().toString(36).slice(2, 10);
  }

  async function handleSubmit(question: string) {
    const userId = newId();
    const loadingId = newId();

    setMessages((prev) => [
      ...prev,
      { kind: "user", text: question, id: userId },
      { kind: "loading", id: loadingId },
    ]);
    setBusy(true);

    try {
      const result = await askShelfPulse({ question });
      setMessages((prev) =>
        prev
          .filter((m) => m.id !== loadingId)
          .concat({ kind: "agent", result, id: newId() })
      );
    } catch (e) {
      const message = 
        e instanceof ApiError
          ? e.message
          : "Something went wrong contacting the backend. Is the server running on port 8000?";
      setMessages((prev) =>
        prev
          .filter((m) => m.id !== loadingId)
          .concat({ kind: "error", message, id: newId() })
       );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex flex-col h-screen max-w-5xl mx-auto">
      <header className="border-b border-default bg-white px-6 py-3 flex items-center justify-between">
        <div>
          <h1 className="text-base font-semibold text-accent">ShelfPulse</h1>
          <p className="text-xs text-muted">CPG sales-insight agent</p>
        </div>
        
          <a href="http://localhost:6006"
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-muted hover:text-accent"
        >
          Open Phoenix →
        </a>
      </header>

      <ChatThread messages={messages} />
      <ChatInput onSubmit={handleSubmit} disabled={busy} />
    </main>
  );
}