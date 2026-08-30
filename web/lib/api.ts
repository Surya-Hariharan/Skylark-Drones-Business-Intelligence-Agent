export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export type BoardSummary = {
  name: string;
  connected: boolean;
  record_count: number;
  fields: string[];
  flags: string[];
  failure_reason: string | null;
};

export type BoardsConfigResponse = { boards: BoardSummary[] };

export async function fetchBoardsConfig(): Promise<BoardsConfigResponse> {
  const res = await fetch(`${API_BASE}/api/config/boards`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load board config (${res.status})`);
  return res.json();
}

export type ChatResponse = {
  kind: "structured" | "text";
  answer?: string | null;
  metrics?: string[] | null;
  insight?: string | null;
  caveats?: string[] | null;
  confidence?: "High" | "Medium" | "Low" | null;
  text?: string | null;
};

export async function postChat(sessionId: string, message: string): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  if (!res.ok) throw new Error(`Chat request failed (${res.status})`);
  return res.json();
}
