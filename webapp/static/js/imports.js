import { formatShortDate } from "./format.js";

const $ = (id) => document.getElementById(id);
const RESULT_LABELS = {
  sensor: "sensor readings",
  scan: "scans",
  fingerstick: "finger-prick readings",
  insulin: "insulin doses",
  priming: "priming shots (kept aside)",
  carbs: "carb entries",
  ketones: "ketone readings",
};

let preview = null;
let lastBatchId = null;
let onImported = () => {};

async function send(path, options) {
  const response = await fetch(`/api/imports${path}`, { credentials: "same-origin", ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function showError(message) {
  $("import-error").textContent = message;
  $("import-error").hidden = !message;
}

function resetImport() {
  preview = null;
  $("import-file").value = "";
  $("import-review").hidden = true;
  $("import-result").hidden = true;
  $("dropzone").hidden = false;
  $("dropzone-title").textContent = "Drop your LibreLink export here, or choose a file";
  showError("");
}

async function upload(file) {
  showError("");
  $("dropzone-title").textContent = `Reading ${file.name}…`;
  $("dropzone").classList.add("busy");
  try {
    const form = new FormData();
    form.append("file", file);
    preview = await send("/preview", { method: "POST", body: form });
    renderReview(preview);
  } catch (error) {
    showError(error.message);
    $("dropzone-title").textContent = "Drop your LibreLink export here, or choose a file";
  } finally {
    $("dropzone").classList.remove("busy");
  }
}

function renderReview(data) {
  $("dropzone").hidden = true;
  $("import-review").hidden = false;
  $("review-format").textContent = `${data.format_label} · ${data.unit}`;
  $("review-file").textContent = data.file_name;
  $("review-range").textContent = data.start ? `${formatShortDate(data.start)} – ${formatShortDate(data.end)}` : "";

  $("review-items").replaceChildren(
    ...data.items.map((item) => {
      const li = document.createElement("li");
      li.innerHTML = `
        <label class="check">
          <input type="checkbox" value="${item.key}" ${item.new > 0 ? "checked" : ""} />
          <span class="review-label"></span>
        </label>
        <span class="review-detail muted"></span>
        <span class="review-count"></span>`;
      li.querySelector(".review-label").textContent = item.label;
      li.querySelector(".review-detail").textContent = item.detail || "";
      const already = item.count - item.new;
      li.querySelector(".review-count").innerHTML =
        `<strong>${item.new.toLocaleString()}</strong> new` + (already > 0 ? `<small>${already.toLocaleString()} already imported</small>` : "");
      return li;
    }),
  );

  const insulin = data.insulin;
  $("review-insulin").hidden = !insulin || insulin.shots === 0;
  if (insulin && insulin.shots) {
    const parts = [];
    if (insulin.priming) parts.push(`${insulin.priming.toLocaleString()} small shots (${insulin.priming_max_units} u or less, just before a bigger dose from the same pen) look like priming and are kept aside.`);
    if (insulin.reclassified) parts.push(`${insulin.reclassified} doses above ${insulin.long_acting_min_units} u were logged as rapid and are counted as long-acting.`);
    $("review-insulin-text").textContent = parts.join(" ");
  }
  $("include-priming").checked = false;

  const notes = [];
  if (data.problems.unreadable_time) notes.push(`${data.problems.unreadable_time.toLocaleString()} rows have an unreadable time and will be skipped.`);
  if (data.problems.glucose_out_of_range) notes.push(`${data.problems.glucose_out_of_range.toLocaleString()} glucose values outside 20–600 mg/dL will be skipped.`);
  if (data.ignored.sensor_events) notes.push(`${data.ignored.sensor_events.toLocaleString()} sensor events (such as sensor starts) contain no glucose and are ignored.`);
  $("review-notes").replaceChildren(...notes.map((text) => Object.assign(document.createElement("li"), { textContent: text })));
  $("import-from").value = "";
}

async function commitImport() {
  if (!preview) return;
  const include = [...$("review-items").querySelectorAll("input:checked")].map((input) => input.value);
  if (!include.length) return showError("Choose at least one type of data to import.");
  const button = $("import-commit");
  button.disabled = true;
  button.textContent = "Importing…";
  showError("");
  try {
    const result = await send("/commit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token: preview.token,
        include,
        include_priming: $("include-priming").checked,
        from_date: $("import-from").value || null,
      }),
    });
    lastBatchId = result.batch_id;
    preview = null;
    renderResult(result.counts);
    onImported();
  } catch (error) {
    showError(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "Import";
  }
}

function renderResult(counts) {
  $("import-review").hidden = true;
  $("import-result").hidden = false;
  const entries = Object.entries(counts).filter(([, n]) => n > 0);
  $("result-list").replaceChildren(
    ...(entries.length
      ? entries.map(([key, n]) => Object.assign(document.createElement("li"), { innerHTML: `<strong>${n.toLocaleString()}</strong> ${RESULT_LABELS[key] || key}` }))
      : [Object.assign(document.createElement("li"), { textContent: "Nothing new: everything in this file was already imported." })]),
  );
  $("result-undo").hidden = !lastBatchId;
}

async function undo(batchId) {
  await send(`/${batchId}/undo`, { method: "POST" });
  onImported();
}

export async function loadImportHistory() {
  const batches = await send("", { method: "GET" });
  const list = $("import-history");
  if (!batches.length) {
    list.replaceChildren(Object.assign(document.createElement("li"), { className: "muted", textContent: "Nothing imported yet." }));
    return;
  }
  list.replaceChildren(
    ...batches.map((batch) => {
      const li = document.createElement("li");
      const total = Object.entries(batch.counts)
        .filter(([key]) => !key.startsWith("glucose_read") && !key.includes("duplicates") && key !== "priming")
        .reduce((sum, [, n]) => sum + n, 0);
      li.innerHTML = `
        <div><strong></strong><span class="muted"></span></div>
        <span class="muted history-count"></span>`;
      li.querySelector("strong").textContent = batch.source === "legacy" ? "Data from the previous app" : batch.file_name || batch.source;
      li.querySelector("div .muted").textContent = ` · ${formatShortDate(batch.imported_at)}${batch.status === "undone" ? " · undone" : ""}`;
      li.querySelector(".history-count").textContent = `${total.toLocaleString()} entries`;
      if (batch.status === "active") {
        const button = Object.assign(document.createElement("button"), { type: "button", className: "btn btn-ghost btn-small", textContent: "Undo" });
        button.addEventListener("click", async () => {
          if (!confirm(`Remove everything imported from ${batch.file_name || batch.source}?`)) return;
          button.disabled = true;
          await undo(batch.id).catch((error) => alert(error.message));
          loadImportHistory();
        });
        li.append(button);
      } else {
        li.classList.add("undone");
      }
      return li;
    }),
  );
}

export function initImports(afterImport) {
  onImported = afterImport;
  const dropzone = $("dropzone");
  $("import-file").addEventListener("change", (event) => event.target.files[0] && upload(event.target.files[0]));
  dropzone.addEventListener("dragover", (event) => { event.preventDefault(); dropzone.classList.add("dragging"); });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragging"));
  dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropzone.classList.remove("dragging");
    if (event.dataTransfer.files[0]) upload(event.dataTransfer.files[0]);
  });
  $("import-cancel").addEventListener("click", resetImport);
  $("import-commit").addEventListener("click", commitImport);
  $("result-undo").addEventListener("click", async () => {
    if (!lastBatchId || !confirm("Remove everything this import added?")) return;
    await undo(lastBatchId).catch((error) => alert(error.message));
    lastBatchId = null;
    resetImport();
  });
}

export function showImportView() {
  if (!preview) resetImport();
}
