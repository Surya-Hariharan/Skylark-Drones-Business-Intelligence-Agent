"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { postChat, type ChatResponse } from "@/lib/api";

type LogEntry =
  | { kind: "user"; text: string }
  | { kind: "text"; text: string }
  | { kind: "structured"; data: ChatResponse };

function getSessionId(): string {
  const key = "skylark_session_id";
  let id = window.localStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    window.localStorage.setItem(key, id);
  }
  return id;
}

export default function ChatPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setSessionId(getSessionId());
  }, []);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [log, busy]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const message = input.trim();
    if (!message || !sessionId || busy) return;

    setLog((prev) => [...prev, { kind: "user", text: message }]);
    setInput("");
    setBusy(true);

    try {
      const data = await postChat(sessionId, message);
      if (data.kind === "structured") {
        setLog((prev) => [...prev, { kind: "structured", data }]);
      } else {
        setLog((prev) => [...prev, { kind: "text", text: data.text ?? "" }]);
      }
    } catch {
      setLog((prev) => [
        ...prev,
        { kind: "text", text: "Network error — could not reach the agent." },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="chat-page">
      <header className="topbar">
        <h1>Skylark BI Agent</h1>
        <p>Ask about pipeline, revenue, operations, or sector performance from live Monday.com data.</p>
        <Link href="/" className="back-link">
          ← Connected boards
        </Link>
      </header>

      <div id="log" ref={logRef}>
        {log.map((entry, i) => (
          <LogItem key={i} entry={entry} />
        ))}
        {busy && <div className="msg agent loading">Thinking...</div>}
      </div>

      <form id="inputRow" onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. What's our open pipeline in Energy?"
          autoComplete="off"
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}

function LogItem({ entry }: { entry: LogEntry }) {
  if (entry.kind === "user") {
    return <div className="msg user">{entry.text}</div>;
  }
  if (entry.kind === "text") {
    return (
      <div className="msg agent">
        <div className="answer">{entry.text}</div>
      </div>
    );
  }

  const data = entry.data;
  return (
    <div className="msg agent">
      <div className="answer">{data.answer ?? ""}</div>

      {data.metrics && data.metrics.length > 0 && (
        <>
          <div className="section-title">Key metrics</div>
          <ul>
            {data.metrics.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </>
      )}

      {data.insight && (
        <>
          <div className="section-title">Insight</div>
          <div>{data.insight}</div>
        </>
      )}

      {data.caveats && data.caveats.length > 0 && (
        <>
          <div className="section-title">Data quality</div>
          <ul>
            {data.caveats.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </>
      )}

      {data.confidence && (
        <div className={`confidence ${data.confidence}`}>{data.confidence} confidence</div>
      )}
    </div>
  );
}
