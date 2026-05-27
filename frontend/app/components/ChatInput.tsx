"use client";

import { useState } from "react";

interface ChatInputProps {
    onSubmit: (question: string) => void;
    disabled: boolean;
}

const EXAMPLE_QUESTIONS = [
  "Top underperforming beverage SKUs in Northeast last quarter",
  "Promo lift on snacks over the last 8 weeks",
  "Flag any out-of-stock risk in the next 30 days",
];

export function ChatInput({ onSubmit, disabled}: ChatInputProps) {
    const [value, setValue] = useState("");

    function handleSubmit() {
        const trimmed = value.trim();
        if (!trimmed || disabled) return;
        onSubmit(trimmed);
        setValue("");
    }

    function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    }

    return (
    <div className="border-t border-default bg-white px-4 py-3">
      {/* Example chips */}
      <div className="flex flex-wrap gap-2 mb-3">
        {EXAMPLE_QUESTIONS.map((q) => (
          <button
            key={q}
            onClick={() => !disabled && setValue(q)}
            disabled={disabled}
            className="text-xs px-3 py-1.5 border border-default rounded-full text-muted hover:text-accent hover:border-accent transition-colors disabled:opacity-50"
          >
            {q.length > 50 ? q.slice(0, 47) + "..." : q}
          </button>
        ))}
      </div>

      {/* Input + button */}
      <div className="flex gap-2 items-end">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder="Ask about CPG sales, promos, regions, SKUs..."
          rows={1}
          className="flex-1 resize-none border border-default rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-accent transition-colors disabled:opacity-50 max-h-32"
        />
        <button
          onClick={handleSubmit}
          disabled={disabled || !value.trim()}
          className="px-5 py-2.5 bg-accent text-white rounded-xl text-sm font-medium hover:opacity-90 disabled:opacity-40 transition-opacity"
        >
          Send
        </button>
      </div>
      <p className="text-[10px] text-muted mt-2">
        Press Enter to send, Shift+Enter for newline. Responses take 20–70 seconds.
      </p>
    </div>
  );
}
