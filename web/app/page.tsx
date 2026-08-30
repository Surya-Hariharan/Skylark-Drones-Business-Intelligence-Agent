"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchBoardsConfig, type BoardSummary } from "@/lib/api";

export default function SetupPage() {
  const [boards, setBoards] = useState<BoardSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchBoardsConfig()
      .then((data) => setBoards(data.boards))
      .catch((err) => setError(err instanceof Error ? err.message : "Unknown error"));
  }, []);

  const allConnected = boards !== null && boards.every((b) => b.connected);

  return (
    <main className="setup">
      <header className="topbar">
        <h1>Skylark BI Agent</h1>
        <p>Confirm what&apos;s connected before you start chatting.</p>
      </header>

      <div className="content">
        {error && (
          <div className="banner error">Could not reach the backend: {error}</div>
        )}

        {!boards && !error && <p className="loading">Checking connected boards…</p>}

        {boards && (
          <div className="cards">
            {boards.map((board) => (
              <BoardCard key={board.name} board={board} />
            ))}
          </div>
        )}

        <Link
          href="/chat"
          className={`start-btn ${allConnected ? "" : "start-btn-warning"}`}
          aria-disabled={!boards}
        >
          {boards ? (allConnected ? "Start chatting →" : "Start chatting anyway →") : "Loading…"}
        </Link>
      </div>
    </main>
  );
}

function BoardCard({ board }: { board: BoardSummary }) {
  if (!board.connected) {
    return (
      <section className="card card-failed">
        <div className="card-head">
          <h2>{board.name}</h2>
          <span className="status status-failed">Not connected</span>
        </div>
        <p className="failure">{board.failure_reason}</p>
      </section>
    );
  }

  return (
    <section className="card">
      <div className="card-head">
        <h2>{board.name}</h2>
        <span className="status status-ok">Connected</span>
      </div>
      <p className="record-count">{board.record_count.toLocaleString()} records</p>

      {board.fields.length > 0 && (
        <>
          <div className="section-title">Mapped fields</div>
          <div className="chips">
            {board.fields.map((field) => (
              <span className="chip" key={field}>
                {field}
              </span>
            ))}
          </div>
        </>
      )}

      {board.flags.length > 0 && (
        <>
          <div className="section-title">Data quality</div>
          <ul className="flags">
            {board.flags.map((flag) => (
              <li key={flag}>{flag}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
