"use client";

import { useEffect, useState } from "react";
import { askShelfPulse, verifyPassword, ApiError } from "@/lib/api";
import { ChatMessage, ChatThread } from "./components/ChatThread";
import { ChatInput } from "./components/ChatInput";
import { Watermark } from "./components/Watermark";

const PW_STORAGE_KEY = "sp_pw";

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);

  // Password gate state.
  const [authed, setAuthed] = useState(false);
  const [ready, setReady] = useState(false);
  const [pwInput, setPwInput] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);
  const [authChecking, setAuthChecking] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined" && window.sessionStorage.getItem(PW_STORAGE_KEY)) {
      setAuthed(true);
    }
    setReady(true);
  }, []);

  async function handleUnlock(e: React.FormEvent) {
    e.preventDefault();
    setAuthChecking(true);
    setAuthError(null);
    try {
      const ok = await verifyPassword(pwInput);
      if (ok) {
        window.sessionStorage.setItem(PW_STORAGE_KEY, pwInput);
        setAuthed(true);
      } else {
        setAuthError("Incorrect password.");
      }
    } catch {
      setAuthError("Couldn't reach the server. Please try again in a moment.");
    } finally {
      setAuthChecking(false);
    }
  }

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
      // Session password rejected (e.g. it was changed): drop back to the gate.
      if (e instanceof ApiError && e.status === 401) {
        window.sessionStorage.removeItem(PW_STORAGE_KEY);
        setMessages((prev) => prev.filter((m) => m.id !== loadingId));
        setAuthed(false);
        setAuthError("Your session expired. Please enter the password again.");
        setBusy(false);
        return;
      }
      const message =
        e instanceof ApiError
          ? e.message
          : "Something went wrong contacting the backend.";
      setMessages((prev) =>
        prev
          .filter((m) => m.id !== loadingId)
          .concat({ kind: "error", message, id: newId() })
       );
    } finally {
      setBusy(false);
    }
  }

  if (!ready) return null;

  if (!authed) {
    return (
      <main className="flex h-screen w-full items-center justify-center bg-white px-4">
        <form
          onSubmit={handleUnlock}
          className="w-full max-w-sm rounded-lg border border-default p-6 shadow-sm"
        >
          <h1 className="text-lg font-semibold text-accent">ShelfPulse</h1>
          <p className="mt-1 text-xs text-muted">
            CPG sales-insight agent · enter the password to continue
          </p>
          <input
            type="password"
            value={pwInput}
            onChange={(e) => setPwInput(e.target.value)}
            placeholder="Password"
            autoFocus
            className="mt-4 w-full rounded-md border border-default px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          />
          {authError && (
            <p className="mt-2 text-xs text-red-600">{authError}</p>
          )}
          <button
            type="submit"
            disabled={authChecking || pwInput.length === 0}
            className="mt-4 w-full rounded-md bg-accent px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {authChecking ? "Checking…" : "Unlock"}
          </button>
        </form>
      </main>
    );
  }

  return (
    <main className="flex flex-col h-screen w-full">
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
      <Watermark />
    </main>
  );
}