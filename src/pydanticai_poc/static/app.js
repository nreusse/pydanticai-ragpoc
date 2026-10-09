/* AG-UI over POST SSE. All source/model content is inserted as text, never HTML. */
const $ = (id) => document.getElementById(id);
let conversationId = null;
let controller = null;
let receivedAnswer = false;
let finished = false;

function selectedSources() {
  return [...document.querySelectorAll("[data-source]:checked")].map((el) => el.value);
}

async function loadSources() {
  $("send").disabled = true;
  try {
    const response = await fetch("/api/sources");
    if (!response.ok) throw new Error("Quellen konnten nicht geladen werden.");
    const records = await response.json();
    $("source-options").replaceChildren();
    records.forEach((record) => {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = record.id;
      input.dataset.source = "";
      input.checked = true;
      input.addEventListener("change", () => busy(false));
      label.append(input, document.createTextNode(" " + record.name));
      $("source-options").append(label);
    });
    if (!records.length) $("source-options").textContent = "Keine Quellen verfügbar.";
    busy(false);
  } catch (error) {
    $("source-options").textContent = error.message;
  }
}

async function loadUser() {
  try {
    const response = await fetch("/api/me");
    if (!response.ok) throw new Error("Benutzerkontext nicht verfügbar");
    const user = await response.json();
    $("user-context").textContent = `${user.display_name} · Rollen: ${user.roles.join(", ") || "keine"}`;
  } catch {
    $("user-context").textContent = "Benutzerkontext nicht verfügbar";
  }
}

loadUser();
loadSources();

function message(role, text, error = false) {
  $("empty")?.remove();
  const row = document.createElement("div");
  row.className = `message ${role}${error ? " error" : ""}`;
  const label = document.createElement("div");
  label.className = "role";
  label.textContent = role === "user" ? "DU" : "QUELLENWERK";
  const content = document.createElement("div");
  content.textContent = text;
  row.append(label, content);
  $("messages").append(row);
  row.scrollIntoView({ block: "nearest" });
}

function busy(value) {
  $("send").disabled = value || !selectedSources().length;
  document.querySelectorAll("[data-source]").forEach((el) => { el.disabled = value; });
  $("question").disabled = value;
  $("reset").disabled = value;
  $("stop").hidden = !value;
  document.querySelectorAll("[data-question]").forEach((el) => { el.disabled = value; });
}

function step(text) {
  const row = document.createElement("li");
  row.textContent = text;
  $("steps").append(row);
  row.scrollIntoView({ block: "nearest" });
}

function sources(records) {
  $("sources").replaceChildren();
  if (!records.length) {
    $("sources").textContent = "Keine ausreichenden Belege gefunden.";
  }
  records.forEach((record) => {
    const row = document.createElement("div");
    row.className = "source";
    const link = document.createElement("a");
    const url = new URL(record.url);
    if (url.protocol !== "https:") return;
    link.href = url.href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = `[${record.evidence_id}] ${record.title}`;
    const meta = document.createElement("p");
    meta.textContent = `${record.source_id} · ${record.locator}${record.truncated ? " · gekürzt" : ""}`;
    const detail = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = "Gelesenen Auszug anzeigen";
    const excerpt = document.createElement("p");
    excerpt.textContent = record.text;
    detail.append(summary, excerpt);
    row.append(link, meta, detail);
    $("sources").append(row);
  });
}

function event(data) {
  if (data.type === "CUSTOM" && data.name === "progress") step(data.value.message);
  if (data.type === "CUSTOM" && data.name === "answer_ready") {
    receivedAnswer = true;
    message("assistant", data.value.answer.text);
    sources(data.value.sources);
  }
  if (data.type === "RUN_ERROR") throw new Error(data.message || "Recherche fehlgeschlagen.");
  if (data.type === "RUN_FINISHED") {
    finished = true;
    $("state").textContent = "Abgeschlossen";
  }
  // Raw tool arguments, intermediate answers and reasoning stay out of the UI.
}

async function consume(response) {
  if (!response.body) throw new Error("Streaming wird vom Browser nicht unterstützt.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  function frames() {
    // Split frames only after complete blank lines; supports CRLF and UTF-8 chunks.
    let match;
    while ((match = /\r?\n\r?\n/.exec(buffer))) {
      const frame = buffer.slice(0, match.index);
      buffer = buffer.slice(match.index + match[0].length);
      const payload = frame.split(/\r?\n/).filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).replace(/^ /, "")).join("\n");
      if (payload) event(JSON.parse(payload));
    }
  }
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      frames();
    }
    buffer += decoder.decode();
    frames();
    if (!finished || !receivedAnswer) throw new Error("Die Recherche wurde nicht vollständig übertragen.");
  } finally {
    await reader.cancel();
    reader.releaseLock();
  }
}

$("form").addEventListener("submit", async (submit) => {
  submit.preventDefault();
  const question = $("question").value.trim();
  if (!question || controller || !selectedSources().length) return;
  controller = new AbortController();
  busy(true);
  receivedAnswer = false;
  finished = false;
  $("steps").replaceChildren();
  $("sources").textContent = "Recherche läuft …";
  $("state").textContent = "In Bearbeitung";
  message("user", question);
  try {
    if (!conversationId) {
      const session = await fetch("/api/conversations", { method: "POST", signal: controller.signal });
      if (!session.ok) throw new Error("Unterhaltung konnte nicht gestartet werden.");
      conversationId = (await session.json()).conversation_id;
    }
    const response = await fetch("/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId, message: question, source_ids: selectedSources() }),
      signal: controller.signal,
    });
    if (!response.ok) {
      if (response.status === 404) conversationId = null;
      throw new Error((await response.json()).detail || "Anfrage fehlgeschlagen.");
    }
    await consume(response);
    $("question").value = "";
  } catch (error) {
    const text = error.name === "AbortError" ? "Recherche abgebrochen."
      : error instanceof TypeError ? "Verbindung zur Anwendung unterbrochen. Prüfe den Webserver."
      : error.message;
    $("state").textContent = error.name === "AbortError" ? "Abgebrochen" : "Fehlgeschlagen";
    step(text);
    message("assistant", text, true);
    if (!receivedAnswer) $("sources").textContent = "Keine geprüfte Antwort vorhanden.";
  } finally {
    controller = null;
    busy(false);
    $("question").focus();
  }
});
$("stop").addEventListener("click", () => controller?.abort());
$("reset").addEventListener("click", () => {
  conversationId = null;
  $("messages").replaceChildren();
  $("sources").textContent = "Hier erscheinen die Belege der nächsten Antwort.";
  $("steps").replaceChildren();
  $("state").textContent = "Bereit";
  $("question").value = "";
});
document.querySelectorAll("[data-question]").forEach((button) => {
  button.addEventListener("click", () => {
    $("question").value = button.dataset.question;
    $("question").focus();
  });
});
