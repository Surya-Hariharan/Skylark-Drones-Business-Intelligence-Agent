function getSessionId() {
  let id = localStorage.getItem("skylark_session_id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("skylark_session_id", id);
  }
  return id;
}

const sessionId = getSessionId();
const log = document.getElementById("log");
const form = document.getElementById("inputRow");
const input = document.getElementById("messageInput");

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderUserMessage(text) {
  const msg = el("div", "msg user", text);
  log.appendChild(msg);
}

function renderAgentText(text) {
  const msg = el("div", "msg agent");
  msg.appendChild(el("div", "answer", text));
  log.appendChild(msg);
}

function renderAgentStructured(data) {
  const msg = el("div", "msg agent");
  msg.appendChild(el("div", "answer", data.answer || ""));

  if (data.metrics && data.metrics.length) {
    msg.appendChild(el("div", "section-title", "Key metrics"));
    const ul = el("ul");
    data.metrics.forEach((m) => ul.appendChild(el("li", null, m)));
    msg.appendChild(ul);
  }

  if (data.insight) {
    msg.appendChild(el("div", "section-title", "Insight"));
    msg.appendChild(el("div", null, data.insight));
  }

  if (data.caveats && data.caveats.length) {
    msg.appendChild(el("div", "section-title", "Data quality"));
    const ul = el("ul");
    data.caveats.forEach((c) => ul.appendChild(el("li", null, c)));
    msg.appendChild(ul);
  }

  if (data.confidence) {
    msg.appendChild(el("div", `confidence ${data.confidence}`, `${data.confidence} confidence`));
  }

  log.appendChild(msg);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  renderUserMessage(message);
  input.value = "";
  input.disabled = true;

  const loadingMsg = el("div", "msg agent loading", "Thinking...");
  log.appendChild(loadingMsg);
  log.scrollTop = log.scrollHeight;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message }),
    });
    const data = await response.json();
    loadingMsg.remove();

    if (!response.ok) {
      renderAgentText("Something went wrong talking to the agent. Please try again.");
    } else if (data.kind === "structured") {
      renderAgentStructured(data);
    } else {
      renderAgentText(data.text || "");
    }
  } catch (err) {
    loadingMsg.remove();
    renderAgentText("Network error — could not reach the agent.");
  }

  input.disabled = false;
  input.focus();
  log.scrollTop = log.scrollHeight;
});
