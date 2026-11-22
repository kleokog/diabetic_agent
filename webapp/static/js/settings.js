import { apiGet, apiPut } from "./api.js";

const FORMS = {
  "form-range": ["target_low", "target_high", "cv_unstable_pct"],
  "form-profile": ["name", "diabetes_type", "rapid_insulin_name", "long_insulin_name"],
  "form-brief": ["coach_brief"],
  "form-insulin": ["long_acting_min_units", "priming_max_units", "priming_window_min"],
};

const DEFAULT_LABELS = ["Breakfast", "Lunch", "Dinner", "Meal 4", "Meal 5", "Meal 6"];
const DEFAULT_TIMES = {
  weekday: ["08:00", "13:00", "20:00", "16:00", "18:00", "21:00"],
  weekend: ["09:00", "13:30", "20:00", "16:00", "18:00", "21:00"],
};

let onSaved = () => {};
let mealSchedule = null;

export async function loadSettings() {
  const settings = await apiGet("/settings");
  for (const [formId, fields] of Object.entries(FORMS)) {
    const form = document.getElementById(formId);
    for (const field of fields) form.elements[field].value = settings[field] ?? "";
  }
  mealSchedule = settings.meal_schedule || null;
  renderMealSchedule(mealSchedule);
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

  const mealForm = document.getElementById("form-meals");
  if (mealForm) {
    mealForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const message = mealForm.querySelector(".form-message");
      const button = mealForm.querySelector("button[type=submit]");
      button.disabled = true;
      message.classList.remove("error");
      message.textContent = "Saving…";
      try {
        await apiPut("/settings", { meal_schedule: collectMealSchedule() });
        message.textContent = "Saved";
        onSaved();
      } catch (error) {
        message.classList.add("error");
        message.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });
    document.getElementById("weekday_meal_count")?.addEventListener("change", () => {
      resizeMealRows("weekday");
    });
    document.getElementById("weekend_meal_count")?.addEventListener("change", () => {
      resizeMealRows("weekend");
    });
  }
}

function renderMealSchedule(schedule) {
  for (const kind of ["weekday", "weekend"]) {
    const block = schedule?.[kind] || {};
    const count = block.meal_count || 3;
    const select = document.getElementById(`${kind}_meal_count`);
    if (select) select.value = String(count);
    paintMealRows(kind, count, block.meals || []);
  }
}

function resizeMealRows(kind) {
  const count = Number(document.getElementById(`${kind}_meal_count`).value);
  const existing = readMealRows(kind);
  paintMealRows(kind, count, existing);
}

function paintMealRows(kind, count, meals) {
  const root = document.getElementById(`${kind}_meal_rows`);
  if (!root) return;
  root.replaceChildren(
    ...Array.from({ length: count }, (_, i) => {
      const meal = meals[i] || {};
      const row = document.createElement("div");
      row.className = "meal-time-row";
      row.innerHTML = `
        <label class="field"><span class="field-label">Meal ${i + 1}</span>
          <input type="text" data-field="label" maxlength="40" />
        </label>
        <label class="field"><span class="field-label">Time</span>
          <input type="time" data-field="time" required />
        </label>`;
      row.querySelector('[data-field="label"]').value =
        meal.label || DEFAULT_LABELS[i] || `Meal ${i + 1}`;
      row.querySelector('[data-field="time"]').value =
        meal.time || DEFAULT_TIMES[kind][i] || "12:00";
      return row;
    }),
  );
}

function readMealRows(kind) {
  const root = document.getElementById(`${kind}_meal_rows`);
  if (!root) return [];
  return [...root.querySelectorAll(".meal-time-row")].map((row) => ({
    label: row.querySelector('[data-field="label"]').value.trim(),
    time: row.querySelector('[data-field="time"]').value,
  }));
}

function collectMealSchedule() {
  const out = {};
  for (const kind of ["weekday", "weekend"]) {
    const count = Number(document.getElementById(`${kind}_meal_count`).value);
    const meals = readMealRows(kind).slice(0, count);
    out[kind] = { meal_count: count, meals };
  }
  return out;
}

function updateBriefCount() {
  const value = document.getElementById("form-brief").elements.coach_brief.value;
  document.getElementById("brief-count").textContent = `${value.length.toLocaleString()} / 4,000`;
}
