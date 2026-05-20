const log = document.getElementById("chatLog");
const remaining = document.getElementById("messageRemaining");

function bubble(text, who) {
  const node = document.createElement("div");
  node.className = `bubble ${who}`;
  node.textContent = text;
  log.appendChild(node);
  log.scrollTop = log.scrollHeight;
}

async function loadHistory() {
  const res = await fetch("/api/ai/history");
  const rows = await res.json();
  document.getElementById("insightHistory").innerHTML = rows.map((row) => `<div class="insight-item"><strong>${row.insight_type}</strong><br>${row.content}</div>`).join("") || "<p>No insights generated yet.</p>";
}

document.getElementById("chatForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = document.getElementById("chatMessage");
  const message = input.value.trim();
  if (!message) return;
  bubble(message, "user");
  input.value = "";
  const res = await fetch("/api/ai/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  const data = await res.json();
  bubble(data.reply || data.error, "bot");
  remaining.textContent = `${data.remaining ?? 0} messages remaining today`;
});

document.getElementById("weeklySummaryBtn").addEventListener("click", async () => {
  const box = document.getElementById("weeklySummary");
  box.textContent = "Generating...";
  const res = await fetch("/api/ai/weekly-summary", { method: "POST" });
  const data = await res.json();
  box.textContent = data.content || data.error;
  await loadHistory();
});

loadHistory();
