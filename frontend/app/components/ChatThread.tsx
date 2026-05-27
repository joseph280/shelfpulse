"use client";

import { useEffect, useRef } from "react";
import { AgentResponse } from "./AgentResponse";
import { RefusalCard } from "./RefusalCard";
import { LoadingCard } from "./LoadingCard";
import { UserMessage } from "./UserMessage";
import { isRefusal } from "@/lib/types";
import type { AskResult } from "@/lib/types";

export type ChatMessage =
  | { kind: "user"; text: string; id: string }
  | { kind: "agent"; result: AskResult; id: string }
  | { kind: "loading"; id: string }
  | { kind: "error"; message: string; id: string };

interface ChatThreadProps {
  messages: ChatMessage[];
}

export function ChatThread({ messages }: ChatThreadProps) {
    const bottomRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom on new messages
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages.length]);

    if (messages.length === 0) {
       return (
      <div className="flex-1 flex items-center justify-center px-4">
        <div className="text-center max-w-md">
          <h2 className="text-xl font-semibold text-accent mb-2">ShelfPulse</h2>
          <p className="text-sm text-muted">
            Ask about CPG sales performance, promotional lift, stockout risk,
            or anything in the warehouse. Pick a sample below or type your own.
          </p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 max-w-3xl mx-auto w-full">
      {messages.map((msg) => {
        switch (msg.kind) {
          case "user":
            return <UserMessage key={msg.id} text={msg.text} />;
          case "loading":
            return <LoadingCard key={msg.id} />;
          case "agent":
            return isRefusal(msg.result) ? (
              <RefusalCard key={msg.id} refusal={msg.result} />
            ) : (
              <AgentResponse key={msg.id} response={msg.result} />
            );
          case "error":
            return (
              <div key={msg.id} className="flex justify-start mb-4">
                <div className="max-w-[80%] bg-red-50 border border-red-200 rounded-2xl px-4 py-3">
                  <p className="text-sm text-red-900">{msg.message}</p>
                </div>
              </div>
            );
        }
      })}
      <div ref={bottomRef} />
    </div>
  );
}