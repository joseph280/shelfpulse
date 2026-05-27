interface UserMessageProps {
    text: string;
}

export function UserMessage({ text }: UserMessageProps) {
    return (
    <div className="flex justify-end mb-4">
      <div className="max-w-[80%] bg-user-bubble rounded-2xl rounded-tr-md px-4 py-3">
        <p className="text-sm leading-relaxed">{text}</p>
      </div>
    </div>
  );
}