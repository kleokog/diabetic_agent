import { apiGet, apiPut } from "./api.js";

const FORMS = {
  "form-range": ["target_low", "target_high"],
  "form-profile": ["name", "diabetes_type", "rapid_insulin_name", "long_insulin_name"],
  "form-brief": ["coach_brief"],
  "form-insulin": ["long_acting_min_units", "priming_max_units", "priming_window_min"],
};

let onSaved = () => {};

export async function loadSettings() {
  const settings = await apiGet("/settings");
  for (const [formId, fields] of Object.entries(FORMS)) {
    const form = document.getElementById(formId);
    for (const field of fields) form.elements[field].value = settings[field] ?? "";
  }
  updateBriefCount();
}

export function initSettings(afterSave) {
  onSaved = afterSave;
  for (const [formId, fields] of Object.entries(FORMS)) {
    const form = document.getElementById(formId);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const message = form.querySelector(".form-message");
      const button = form.querySelector("button[type=submit]");
      const values = Object.fromEntries(fields.map((f) => [f, form.elements[f].value]));
      button.disabled = true;
      message.classList.remove("error");
      message.textContent = "Saving…";
      try {
        await apiPut("/settings", values);
        message.textContent = "Saved";
        onSaved();
      } catch (error) {
        message.classList.add("error");
        message.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });
  }
  document.getElementById("form-brief").elements.coach_brief.addEventListener("input", updateBriefCount);
}

function updateBriefCount() {
  const value = document.getElementById("form-brief").elements.coach_brief.value;
  document.getElementById("brief-count").textContent = `${value.length.toLocaleString()} / 4,000`;
}
