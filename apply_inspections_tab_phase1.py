#!/usr/bin/env python3
"""
apply_inspections_tab_phase1.py

Phase 1 of the Inspection Templates feature: a new top-level "Inspections"
tab that bulk-creates inspection templates (no triggers, no Q&A yet —
those come in later phases).

What it does:
  - Adds an "Inspections" tab next to PPM / Assets / Inventory / Portfolio
  - One-time "Defaults" panel for org-wide constants (formId, stateFlowId,
    category, priority, moduleState, assignmentType, templateType, type,
    totalPages, creationType) — values mirror the user's Deluge script
  - A grid for per-row data: Name, Scope (Single|Multiple), Sites, Buildings,
    Assigned To, Resource Type, Resource Name
  - Validate-then-import flow matches the rest of the tool
  - One POST per row to /maintenance/api/v3/modules/inspectionTemplate
  - Status column shows Record ID on success

How to run:
  Put next to your index.html, then:
    python3 apply_inspections_tab_phase1.py

Backup: index.html.before-inspections-phase1.bak
"""

import sys
from pathlib import Path

INDEX = Path(__file__).parent / "index.html"
BACKUP = Path(__file__).parent / "index.html.before-inspections-phase1.bak"


def fail(msg):
    print(f"\n[ERROR] {msg}\n\nNo changes written.")
    sys.exit(1)


def replace_once(text, old, new, label):
    if old not in text:
        first = old.strip().split("\n", 1)[0][:80]
        fail(f"Couldn't find expected text for: {label}\n  Looking for: {first!r}")
    if text.count(old) > 1:
        fail(f"'{label}' matched {text.count(old)} places — expected 1.")
    return text.replace(old, new, 1)


# ====================================================================
#                         PATCH FRAGMENTS
# ====================================================================

# --- 1. Tab button (top-level nav) ---
TAB_BUTTON_OLD = """    <button class="tab" data-tab="portfolio">Portfolio</button>
    <button class="tab" data-tab="logs">Record History</button>"""
TAB_BUTTON_NEW = """    <button class="tab" data-tab="portfolio">Portfolio</button>
    <button class="tab" data-tab="inspections">Inspections</button>
    <button class="tab" data-tab="logs">Record History</button>"""

# --- 2. Tab panel HTML (inserted before the Logs heading near bottom) ---
TAB_PANEL_NEW = """
  <!-- ===== Inspection Templates Tab ===== -->
  <div id="tabInspections" class="tab-panel hidden">
    <div class="panel" style="padding: 12px 14px;">
      <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">
        <div>
          <h3 style="margin:0 0 4px;">Inspection Templates</h3>
          <p class="muted small" style="margin:0;">Bulk-create inspection templates. After they're created, attach triggers and Q&amp;A in the next phases.</p>
        </div>
        <div class="card-actions" style="margin:0;">
          <button class="btn ghost" id="btnInspTemplate">Template</button>
          <button class="btn ghost" id="btnInspUpload">Upload</button>
          <input type="file" id="inspExcelInput" accept=".xlsx,.xls,.csv" style="display:none" />
          <button class="btn" id="btnInspNewRow">+ New row</button>
          <button class="btn secondary" id="btnInspValidate">Validate all</button>
          <button class="btn success" id="btnInspImport">Import all</button>
          <button class="btn ghost" id="btnInspRemoveDone">Remove imported</button>
          <button class="btn ghost" id="btnInspClearAll">Clear all</button>
        </div>
      </div>

      <details class="help" open style="margin-top:12px;">
        <summary>Defaults (apply to every row — set once, leave them be)</summary>
        <div class="help-body">
          <p class="muted small" style="margin:0 0 8px;">These IDs come from your Facilio account setup. Same values across every row, so set them once here instead of repeating per row. They match the constants in your existing Deluge script.</p>
          <div class="grid-3">
            <label class="field"><span class="lbl">Form ID *</span><input id="inspDefFormId" placeholder="e.g. 26019" /></label>
            <label class="field"><span class="lbl">State Flow ID *</span><input id="inspDefStateFlowId" placeholder="e.g. 244765" /></label>
            <label class="field"><span class="lbl">Module State ID</span><input id="inspDefModuleStateId" placeholder="e.g. 12156" /></label>
            <label class="field"><span class="lbl">Category ID</span><input id="inspDefCategoryId" placeholder="e.g. 403" /></label>
            <label class="field"><span class="lbl">Priority ID</span><input id="inspDefPriorityId" placeholder="e.g. 194" /></label>
            <label class="field"><span class="lbl">Assignment Type</span><input id="inspDefAssignmentType" value="7" /></label>
            <label class="field"><span class="lbl">Template Type</span><input id="inspDefTemplateType" value="2" /></label>
            <label class="field"><span class="lbl">Type</span><input id="inspDefType" value="1" /></label>
            <label class="field"><span class="lbl">Total Pages</span><input id="inspDefTotalPages" value="1" /></label>
            <label class="field"><span class="lbl">Creation Type</span><input id="inspDefCreationType" value="1" /></label>
          </div>
          <div class="card-actions" style="margin-top:4px;">
            <button class="btn ghost" id="btnInspDefaultsSave">Save defaults to this browser</button>
            <span class="muted small" id="inspDefaultsStatus"></span>
          </div>
        </div>
      </details>

      <details class="help" style="margin-top: 6px;">
        <summary>Paste rows from Excel</summary>
        <div class="help-body">
          Header row + data rows. Recognised column names: Name, Description, Scope, Site, Sites, Building, Buildings, Resource Type, Resource, Assigned To, Publish.
          <textarea id="inspBulkPaste" placeholder="Paste rows here..." style="height:90px; margin-top:8px;"></textarea>
          <div class="card-actions" style="margin-top:6px;">
            <button class="btn" id="btnInspBulkParse">Parse &amp; add</button>
            <button class="btn ghost" id="btnInspBulkClear">Clear paste box</button>
          </div>
        </div>
      </details>
    </div>

    <div class="panel" style="padding: 0;">
      <div class="grid-scroll">
        <table class="grid" id="inspGrid">
          <thead><tr id="inspGridHead"></tr></thead>
          <tbody></tbody>
        </table>
      </div>
      <div style="padding: 10px 14px; border-top:1px solid var(--line); display:flex; justify-content:space-between; align-items:center;">
        <span class="muted small" id="inspRowCount">0 rows</span>
        <button class="btn ghost" id="btnInspNewRow2">+ Add row</button>
      </div>
    </div>
  </div>
"""

# Inserted just before the Logs heading
TAB_PANEL_ANCHOR = '  <h3 style="margin: 14px 14px 0;">Logs</h3>'
TAB_PANEL_REPLACEMENT = TAB_PANEL_NEW + "\n" + TAB_PANEL_ANCHOR

# --- 3. State additions ---
STATE_OLD = """  // Portfolio queues (add mode + update mode)
  portQueue: { site: [], building: [], floor: [], space: [] },
  portUpdQueue: { site: [], building: [], floor: [], space: [] },
  activePort: "site",
  activePortMode: "add","""
STATE_NEW = """  // Portfolio queues (add mode + update mode)
  portQueue: { site: [], building: [], floor: [], space: [] },
  portUpdQueue: { site: [], building: [], floor: [], space: [] },
  activePort: "site",
  activePortMode: "add",
  // Inspection Templates queue (Phase 1 — Add only)
  inspQueue: [],
  inspDefaults: null,  // loaded from localStorage on app start"""

# --- 4. switchTab body — handle the new tab ---
SWITCHTAB_OLD = """  $("#tabPortfolio")?.classList.toggle("hidden", name !== "portfolio");
  $("#tabLogs")?.classList.toggle("hidden", name !== "logs");"""
SWITCHTAB_NEW = """  $("#tabPortfolio")?.classList.toggle("hidden", name !== "portfolio");
  $("#tabInspections")?.classList.toggle("hidden", name !== "inspections");
  $("#tabLogs")?.classList.toggle("hidden", name !== "logs");"""

# --- 5. JS module — column defs + helpers + handlers ---
# Inserted right before the closing }); of the DOMContentLoaded block —
# specifically, before the final `});` that ends the window.addEventListener.
JS_MODULE = """
// ---------- Inspection Templates (Phase 1: Add) ----------
//
// Mirrors the user's existing Deluge script: one POST per row to
// /maintenance/api/v3/modules/inspectionTemplate with org-wide constants
// (form, stateFlow, category, priority, moduleState, type flags) coming
// from a one-time Defaults panel, and per-row fields (name, sites,
// buildings, assignedTo, resource) coming from the grid.

const INSP_DEFAULTS_LS_KEY = "ppm-manager.inspections.defaults";

const INSP_COLUMN_DEFS = [
  { key:"_num",        label:"#",              kind:"num",     width:"w-num",    sticky:true },
  { key:"_status",     label:"Status",         kind:"status",  width:"w-status", sticky:true },
  { key:"name",        label:"Name *",         kind:"text",    width:"w-md" },
  { key:"description", label:"Description",    kind:"text",    width:"w-lg" },
  { key:"scope",       label:"Scope *",        kind:"select",  width:"w-sm",
    options:[{v:"single",l:"Single"},{v:"multiple",l:"Multiple"}] },
  { key:"sites",       label:"Sites *",        kind:"text",    width:"w-md", picklist:"site",
    placeholder:"comma-sep for Multiple" },
  { key:"buildings",   label:"Buildings",      kind:"text",    width:"w-md", picklist:"building",
    placeholder:"required when Multiple" },
  { key:"resourceType",label:"Resource Type",  kind:"select",  width:"w-sm",
    options:[{v:"",l:""},{v:"asset",l:"Asset"},{v:"site",l:"Site"},{v:"building",l:"Building"},{v:"floor",l:"Floor"},{v:"space",l:"Space"}] },
  { key:"resource",    label:"Resource",       kind:"text",    width:"w-md",
    placeholder:"only for Single scope" },
  { key:"assignedTo",  label:"Assigned To",    kind:"text",    width:"w-md", picklist:"users",
    placeholder:"user email" },
  { key:"publish",     label:"Publish?",       kind:"select",  width:"w-sm",
    options:[{v:"no",l:"No (draft)"},{v:"yes",l:"Yes"}] },
  { key:"_recordId",   label:"Record ID",      kind:"readonly",width:"w-sm" },
  { key:"_actions",    label:"",               kind:"actions", width:"w-actions" }
];

function blankInspRow() {
  return {
    name:"", description:"", scope:"single",
    sites:"", buildings:"",
    resourceType:"", resource:"",
    assignedTo:"",
    publish:"no",
    _recordId:""
  };
}

function loadInspDefaults() {
  try {
    const raw = localStorage.getItem(INSP_DEFAULTS_LS_KEY);
    if (raw) state.inspDefaults = JSON.parse(raw);
  } catch (_) {}
  state.inspDefaults = state.inspDefaults || {};
  // Apply to UI
  const map = {
    formId: "inspDefFormId",
    stateFlowId: "inspDefStateFlowId",
    moduleStateId: "inspDefModuleStateId",
    categoryId: "inspDefCategoryId",
    priorityId: "inspDefPriorityId",
    assignmentType: "inspDefAssignmentType",
    templateType: "inspDefTemplateType",
    type: "inspDefType",
    totalPages: "inspDefTotalPages",
    creationType: "inspDefCreationType"
  };
  for (const [k, id] of Object.entries(map)) {
    const el = document.getElementById(id);
    if (!el) continue;
    if (state.inspDefaults[k] != null && state.inspDefaults[k] !== "") el.value = state.inspDefaults[k];
  }
}

function saveInspDefaultsFromUi() {
  const grab = id => document.getElementById(id)?.value.trim() || "";
  const obj = {
    formId: grab("inspDefFormId"),
    stateFlowId: grab("inspDefStateFlowId"),
    moduleStateId: grab("inspDefModuleStateId"),
    categoryId: grab("inspDefCategoryId"),
    priorityId: grab("inspDefPriorityId"),
    assignmentType: grab("inspDefAssignmentType") || "7",
    templateType: grab("inspDefTemplateType") || "2",
    type: grab("inspDefType") || "1",
    totalPages: grab("inspDefTotalPages") || "1",
    creationType: grab("inspDefCreationType") || "1"
  };
  state.inspDefaults = obj;
  localStorage.setItem(INSP_DEFAULTS_LS_KEY, JSON.stringify(obj));
  const el = document.getElementById("inspDefaultsStatus");
  if (el) {
    el.textContent = "✓ saved to this browser";
    setTimeout(() => { if (el.textContent === "✓ saved to this browser") el.textContent = ""; }, 3000);
  }
}

function renderInspQueue() {
  const head = $("#inspGridHead");
  if (!head) return;
  const cols = INSP_COLUMN_DEFS;
  const table = head.closest("table");
  const existingColgroup = table.querySelector(":scope > colgroup");
  if (existingColgroup) existingColgroup.remove();
  delete head.dataset.built;
  buildGridHead(head, cols);
  const tbody = $("#inspGrid tbody");
  tbody.innerHTML = state.inspQueue.map((row, idx) =>
    `<tr>` + cols.map(c => renderCell(c, row, idx)).join("") + `</tr>`
  ).join("");
  $("#inspRowCount").textContent = `${state.inspQueue.length} row${state.inspQueue.length === 1 ? "" : "s"}`;
}

async function validateInspRow(row) {
  const errors = [];
  // Required defaults
  const d = state.inspDefaults || {};
  if (!d.formId) errors.push("Defaults: Form ID is missing — fill the Defaults panel at the top");
  if (!d.stateFlowId) errors.push("Defaults: State Flow ID is missing");

  if (!row.name) errors.push("Name is required");
  if (!row.scope) errors.push("Scope is required (Single or Multiple)");
  if (!row.sites) errors.push("At least one Site is required");

  if (row.scope === "multiple" && !row.buildings && !row.resource) {
    // Buildings list typically required for Multiple; not always — soft warn
  }
  if (row.scope === "single" && !row.resource) {
    errors.push("Resource is required for Single scope (or use Multiple)");
  }

  // Resolve site IDs
  try {
    row._siteIds = [];
    for (const name of row.sites.split(",").map(s => s.trim()).filter(Boolean)) {
      const id = await portFindIdByName("site", name);
      if (!id) throw new Error(`Site not found: ${name}`);
      row._siteIds.push(id);
    }
    row._buildingIds = [];
    if (row.buildings) {
      for (const name of row.buildings.split(",").map(s => s.trim()).filter(Boolean)) {
        const id = await portFindIdByName("building", name);
        if (!id) throw new Error(`Building not found: ${name}`);
        row._buildingIds.push(id);
      }
    }
    // Assigned To
    row._assignedToId = null;
    if (row.assignedTo) {
      row._assignedToId = await findInList("users", "users", row.assignedTo);
      if (!row._assignedToId) throw new Error(`Assigned-to user not found: ${row.assignedTo}`);
    }
    // Resource (Single scope) — module varies by Resource Type
    row._resourceId = null;
    if (row.scope === "single" && row.resource) {
      const rt = (row.resourceType || "").toLowerCase() || "building";
      const moduleName = rt === "asset" ? "asset" :
                         rt === "site" ? "site" :
                         rt === "floor" ? "floor" :
                         rt === "space" ? "space" : "building";
      row._resourceId = await portFindIdByName(moduleName, row.resource);
      if (!row._resourceId) throw new Error(`Resource "${row.resource}" not found in ${moduleName} module`);
    }
    // Multiple scope: resource defaults to the first building (matches Deluge script)
    if (row.scope === "multiple" && !row._resourceId && row._buildingIds.length) {
      row._resourceId = row._buildingIds[0];
    } else if (row.scope === "multiple" && !row._resourceId && row._siteIds.length) {
      row._resourceId = row._siteIds[0];
    }
  } catch (e) {
    errors.push(e.message);
  }

  if (errors.length) { row.status = { kind:"error", text: errors.join("; ") }; return false; }
  row.status = { kind:"valid", text:"Valid" };
  return true;
}

function buildInspRecord(row) {
  const d = state.inspDefaults || {};
  const out = {
    name: row.name,
    description: row.description || row.name,
    status: true,
    isPublished: row.publish === "yes",
    creationType: Number(d.creationType || 1),
    assignmentType: Number(d.assignmentType || 7),
    templateType: Number(d.templateType || 2),
    type: Number(d.type || 1),
    totalPages: Number(d.totalPages || 1),
    formId: Number(d.formId),
    stateFlowId: Number(d.stateFlowId)
  };
  if (d.categoryId)    out.category    = { id: Number(d.categoryId) };
  if (d.priorityId)    out.priority    = { id: Number(d.priorityId) };
  if (d.moduleStateId) out.moduleState = { id: Number(d.moduleStateId) };
  if (row._siteIds && row._siteIds.length)         out.sites = row._siteIds.map(id => ({ id }));
  if (row._buildingIds && row._buildingIds.length) out.buildings = row._buildingIds.map(id => ({ id }));
  if (row._assignedToId)                            out.assignedTo = { id: row._assignedToId };
  if (row._resourceId)                              out.resource = { id: row._resourceId };
  return out;
}

async function importInspBatch(rows) {
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const rec = buildInspRecord(row);
    row.status = { kind:"running", text:"Creating template…" };
    renderInspQueue();
    try {
      const r = await api("POST",
        "maintenance/api/v3/modules/inspectionTemplate",
        { moduleName: "inspectionTemplate", data: rec });
      const root = r?.data || {};
      const ret = root.inspectionTemplate || root.list || root.data || root;
      const arr = Array.isArray(ret) ? ret : (ret ? [ret] : []);
      const newId = arr[0]?.id || ret?.id;
      if (newId) row._recordId = newId;
      row.status = { kind:"success", text: newId ? `Created (id ${newId})` : "Created" };
    } catch (e) {
      let detail = e.message;
      if (e.body) {
        const msg = e.body.message || e.body.title || JSON.stringify(e.body);
        detail = String(msg).slice(0, 220);
      }
      row.status = { kind:"error", text: "Create failed: " + detail };
    }
    renderInspQueue();
  }
}

// ---------- Inspection Templates header mapping (paste/Excel) ----------
const INSP_HEADER_ALIASES = {
  "name": "name", "template name": "name", "inspection name": "name",
  "description": "description", "desc": "description",
  "scope": "scope",
  "site": "sites", "sites": "sites",
  "building": "buildings", "buildings": "buildings",
  "resource type": "resourceType", "resource kind": "resourceType",
  "resource": "resource", "resource name": "resource",
  "assigned to": "assignedTo", "assignee": "assignedTo", "user": "assignedTo",
  "publish": "publish", "publish?": "publish"
};

function inspAddFromTabular(lines, delim) {
  const headers = lines[0].split(delim).map(h => h.trim());
  let added = 0;
  for (let li = 1; li < lines.length; li++) {
    const cells = lines[li].split(delim);
    const row = blankInspRow();
    let hasContent = false;
    headers.forEach((h, i) => {
      const key = INSP_HEADER_ALIASES[h.toLowerCase().trim()];
      if (key && cells[i] != null) {
        row[key] = cells[i].trim();
        if (cells[i].trim()) hasContent = true;
      }
    });
    if (hasContent) { state.inspQueue.push(row); added++; }
  }
  return added;
}

// ---------- Inspection Templates event wiring ----------
(function wireInspectionTab(){
  if (!document.getElementById("inspGrid")) return; // tab not present (patch not applied)
  // Seed with one blank row
  if (state.inspQueue.length === 0) state.inspQueue.push(blankInspRow());
  loadInspDefaults();
  bindGridInputs("#inspGrid",
    () => state.inspQueue,
    () => INSP_COLUMN_DEFS,
    () => blankInspRow(),
    renderInspQueue);

  const addRow = () => { state.inspQueue.push(blankInspRow()); renderInspQueue(); };
  document.getElementById("btnInspNewRow")?.addEventListener("click", addRow);
  document.getElementById("btnInspNewRow2")?.addEventListener("click", addRow);
  document.getElementById("btnInspDefaultsSave")?.addEventListener("click", saveInspDefaultsFromUi);

  document.getElementById("btnInspValidate")?.addEventListener("click", async () => {
    for (const r of state.inspQueue) {
      r.status = { kind:"running", text:"Validating…" }; renderInspQueue();
      await validateInspRow(r); renderInspQueue();
    }
  });

  document.getElementById("btnInspImport")?.addEventListener("click", async () => {
    const valid = [];
    for (const r of state.inspQueue) {
      if (r.status?.kind === "success") continue;
      const ok = await validateInspRow(r);
      if (ok) valid.push(r);
    }
    renderInspQueue();
    if (!valid.length) { showToast("Nothing valid to import"); return; }
    await importInspBatch(valid);
    showToast("Inspection Templates import complete");
  });

  document.getElementById("btnInspRemoveDone")?.addEventListener("click", () => {
    state.inspQueue = state.inspQueue.filter(r => r.status?.kind !== "success");
    if (!state.inspQueue.length) state.inspQueue.push(blankInspRow());
    renderInspQueue();
  });
  document.getElementById("btnInspClearAll")?.addEventListener("click", () => {
    if (confirm("Clear all Inspection rows?")) {
      state.inspQueue = [blankInspRow()];
      renderInspQueue();
    }
  });

  document.getElementById("btnInspBulkParse")?.addEventListener("click", () => {
    const text = document.getElementById("inspBulkPaste").value;
    if (!text.trim()) return showToast("Paste box is empty", "warn");
    const lines = text.replace(/\\r/g, "").split("\\n").filter(l => l.trim());
    if (lines.length < 2) return showToast("Need a header row + data rows", "err");
    const delim = lines[0].includes("\\t") ? "\\t" : ",";
    const added = inspAddFromTabular(lines, delim);
    renderInspQueue();
    showToast(`Added ${added} row(s)`);
  });
  document.getElementById("btnInspBulkClear")?.addEventListener("click", () => {
    document.getElementById("inspBulkPaste").value = "";
  });

  document.getElementById("btnInspTemplate")?.addEventListener("click", () => {
    if (typeof XLSX === "undefined") return showToast("Excel library failed to load", "err");
    const headers = ["Name","Description","Scope","Sites","Buildings","Resource Type","Resource","Assigned To","Publish"];
    const sample = ["DPM Building Inspection Report","Routine monthly inspection","multiple","Investa HQ","Tower A","","","mithun@example.com","no"];
    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.aoa_to_sheet([headers, sample]);
    ws["!cols"] = headers.map(h => ({ wch: Math.max(14, Math.min(28, h.length + 4)) }));
    XLSX.utils.book_append_sheet(wb, ws, "InspectionTemplates");
    XLSX.writeFile(wb, "inspection-templates-template.xlsx");
    showToast("Saved inspection-templates-template.xlsx");
  });
  document.getElementById("btnInspUpload")?.addEventListener("click", () => {
    document.getElementById("inspExcelInput").click();
  });
  document.getElementById("inspExcelInput")?.addEventListener("change", async e => {
    const file = e.target.files[0]; e.target.value = "";
    if (!file || typeof XLSX === "undefined") return;
    const buf = await file.arrayBuffer();
    const wb = XLSX.read(buf, { type: "array" });
    const ws = wb.Sheets[wb.SheetNames[0]];
    const tsv = XLSX.utils.sheet_to_csv(ws, { FS: "\\t" });
    const lines = tsv.replace(/\\r/g, "").split("\\n").filter(l => l.trim());
    if (lines.length < 2) return showToast("File has no data rows", "warn");
    const added = inspAddFromTabular(lines, "\\t");
    renderInspQueue();
    showToast(`Imported ${added} row(s)`);
  });

  renderInspQueue();
})();

"""

# Insertion point — right before the FINAL `});` that ends the
# `window.addEventListener("DOMContentLoaded", () => { ... });` block.
# We anchor to the Disconnect handler's closing braces which precede it.
JS_ANCHOR = """  $("#btnLogout").addEventListener("click", () => {"""


def main():
    if not INDEX.exists():
        fail(f"index.html not found at {INDEX}.")
    original = INDEX.read_text(encoding="utf-8")
    print(f"Read {INDEX} ({len(original):,} bytes)")

    if "INSPECTIONS_PHASE1_APPLIED" in original or "tabInspections" in original:
        fail("Already applied (sentinel / tabInspections present).")

    text = original

    # 1. Tab button
    text = replace_once(text, TAB_BUTTON_OLD, TAB_BUTTON_NEW, "Tab button")

    # 2. Tab panel HTML — insert before the Logs heading
    text = replace_once(text, TAB_PANEL_ANCHOR, TAB_PANEL_REPLACEMENT, "Tab panel")

    # 3. State block
    text = replace_once(text, STATE_OLD, STATE_NEW, "State additions")

    # 4. switchTab
    text = replace_once(text, SWITCHTAB_OLD, SWITCHTAB_NEW, "switchTab branch")

    # 5. JS module — insert before the Disconnect handler (which is one of the
    # last handlers wired in DOMContentLoaded). The wireInspectionTab() IIFE
    # at the end runs immediately and sets everything up.
    text = replace_once(text, JS_ANCHOR,
        "// INSPECTIONS_PHASE1_APPLIED — Inspection Templates feature wired below.\n"
        + JS_MODULE + "\n  " + JS_ANCHOR,
        "JS module insertion before Disconnect handler")

    BACKUP.write_text(original, encoding="utf-8")
    INDEX.write_text(text, encoding="utf-8")
    delta = len(text) - len(original)
    print(f"\n✓ Inspections tab (Phase 1) added.")
    print(f"  Backup: {BACKUP.name}")
    print(f"  New size: {len(text):,} bytes (delta: {delta:+,})")
    print()
    print("Restart `python3 start.py`, hard-refresh the browser.")
    print()
    print("First time using it:")
    print("  1. Click the new 'Inspections' tab.")
    print("  2. Open the 'Defaults' panel at the top.")
    print("  3. Fill formId, stateFlowId, moduleStateId, categoryId, priorityId")
    print("     using the same numbers from your Deluge script (e.g. 26019, 244765,")
    print("     12156, 403, 194). Click 'Save defaults to this browser'.")
    print("  4. Add rows or paste from Excel and Import.")
    print()
    print("Phase 2 (Triggers) and Phase 3 (Q&A) come in follow-up patches.")


if __name__ == "__main__":
    main()
