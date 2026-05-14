#!/usr/bin/env python3
"""
apply_inspections_tab_phase1_v2.py

REVISED Phase 1 patch — uses the actual API payload captured from the
Facilio web UI (not the bloated Deluge constants).

What's different from v1:
  - Defaults panel is trimmed to 5 fields: formId, categoryId, priorityId,
    creationType (default 2), assignmentType (default 5). Everything else
    from the Deluge script was legacy / not required by the API.
  - The POST payload now mirrors the exact UI capture:
      creationType, sites[], buildings[], assignmentType, assetCategory,
      spaceCategory, resource, name, description, category, priority,
      assignedTo, assignmentGroup, triggers, formId, actionFormId,
      mySignatureApplied
  - After the template is created, a default "Page 1" is auto-created in
    the qandaPage module with parent = newly-created template ID. This
    matches what the UI does behind the scenes.

If you previously ran apply_inspections_tab_phase1.py (the v1), this
script will refuse to run — revert that first:
  mv index.html.before-inspections-phase1.bak index.html

How to run:
  cd ~/Documents/GitHub/import-manager
  python3 apply_inspections_tab_phase1_v2.py
"""

import sys
from pathlib import Path

INDEX = Path(__file__).parent / "index.html"
BACKUP = Path(__file__).parent / "index.html.before-inspections-phase1-v2.bak"


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


# --- 1. Tab button (top-level nav) ---
TAB_BUTTON_OLD = """    <button class="tab" data-tab="portfolio">Portfolio</button>
    <button class="tab" data-tab="logs">Record History</button>"""
TAB_BUTTON_NEW = """    <button class="tab" data-tab="portfolio">Portfolio</button>
    <button class="tab" data-tab="inspections">Inspections</button>
    <button class="tab" data-tab="logs">Record History</button>"""

# --- 2. Tab panel HTML — much simpler Defaults panel ---
TAB_PANEL_NEW = """
  <!-- ===== Inspection Templates Tab ===== -->
  <div id="tabInspections" class="tab-panel hidden">
    <div class="panel" style="padding: 12px 14px;">
      <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">
        <div>
          <h3 style="margin:0 0 4px;">Inspection Templates</h3>
          <p class="muted small" style="margin:0;">Bulk-create inspection templates. A default Q&amp;A page is auto-created for each one — questions and triggers come in follow-up phases.</p>
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
        <summary>Defaults (apply to every row — set once)</summary>
        <div class="help-body">
          <p class="muted small" style="margin:0 0 8px;">Five values you need from your Facilio setup. Open one of your existing inspection templates in the Facilio UI, hit Save in DevTools and copy the IDs from the POST payload. They're constant across every template in the same org/module.</p>
          <div class="grid-3">
            <label class="field"><span class="lbl">Form ID *</span><input id="inspDefFormId" placeholder="e.g. 85375" /></label>
            <label class="field"><span class="lbl">Category ID *</span><input id="inspDefCategoryId" placeholder="e.g. 2347" /></label>
            <label class="field"><span class="lbl">Priority ID *</span><input id="inspDefPriorityId" placeholder="e.g. 1176" /></label>
            <label class="field"><span class="lbl">Creation Type</span><input id="inspDefCreationType" value="2" /></label>
            <label class="field"><span class="lbl">Assignment Type</span><input id="inspDefAssignmentType" value="5" /></label>
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
          Header row + data rows. Recognised: Name, Description, Sites, Buildings, Resource Type, Resource, Assigned To, Publish.
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
  // Inspection Templates queue (Phase 1 v2 — Add only, payload matches real UI)
  inspQueue: [],
  inspDefaults: null,"""

# --- 4. switchTab body ---
SWITCHTAB_OLD = """  $("#tabPortfolio")?.classList.toggle("hidden", name !== "portfolio");
  $("#tabLogs")?.classList.toggle("hidden", name !== "logs");"""
SWITCHTAB_NEW = """  $("#tabPortfolio")?.classList.toggle("hidden", name !== "portfolio");
  $("#tabInspections")?.classList.toggle("hidden", name !== "inspections");
  $("#tabLogs")?.classList.toggle("hidden", name !== "logs");"""

# --- 5. JS module — payload + Q&A auto-create ---
JS_MODULE = """
// ---------- Inspection Templates (Phase 1 v2: Add — matches UI payload) ----------
//
// Captured from a real UI POST:
//   POST /maintenance/api/v3/modules/inspectionTemplate
//   body: { moduleName, data: {
//     creationType, sites[], buildings[], assignmentType,
//     assetCategory, spaceCategory, resource, name, description,
//     category, priority, assignedTo, assignmentGroup, triggers,
//     formId, actionFormId, mySignatureApplied
//   }}
// Then a default Q&A page is created:
//   POST /maintenance/api/v3/modules/qandaPage
//   body: { moduleName, data: { name:"Page 1", description:"",
//     parent: <inspectionTemplate id>, position: 1 } }

const INSP_DEFAULTS_LS_KEY = "ppm-manager.inspections.defaults.v2";

const INSP_COLUMN_DEFS = [
  { key:"_num",        label:"#",              kind:"num",     width:"w-num",    sticky:true },
  { key:"_status",     label:"Status",         kind:"status",  width:"w-status", sticky:true },
  { key:"name",        label:"Name *",         kind:"text",    width:"w-md" },
  { key:"description", label:"Description",    kind:"text",    width:"w-lg" },
  { key:"sites",       label:"Sites *",        kind:"text",    width:"w-md", picklist:"site",
    placeholder:"comma-sep for multiple" },
  { key:"buildings",   label:"Buildings",      kind:"text",    width:"w-md", picklist:"building",
    placeholder:"comma-sep" },
  { key:"resourceType",label:"Resource Type",  kind:"select",  width:"w-sm",
    options:[{v:"building",l:"Building"},{v:"asset",l:"Asset"},{v:"site",l:"Site"},{v:"floor",l:"Floor"},{v:"space",l:"Space"}] },
  { key:"resource",    label:"Resource *",     kind:"text",    width:"w-md",
    placeholder:"name or ID; defaults to first building" },
  { key:"assignedTo",  label:"Assigned To",    kind:"text",    width:"w-md", picklist:"users" },
  { key:"_recordId",   label:"Record ID",      kind:"readonly",width:"w-sm" },
  { key:"_qaPageId",   label:"Q&A Page ID",    kind:"readonly",width:"w-sm" },
  { key:"_actions",    label:"",               kind:"actions", width:"w-actions" }
];

function blankInspRow() {
  return {
    name:"", description:"",
    sites:"", buildings:"",
    resourceType:"building", resource:"",
    assignedTo:"",
    _recordId:"", _qaPageId:""
  };
}

function loadInspDefaults() {
  try {
    const raw = localStorage.getItem(INSP_DEFAULTS_LS_KEY);
    if (raw) state.inspDefaults = JSON.parse(raw);
  } catch (_) {}
  state.inspDefaults = state.inspDefaults || {};
  const map = {
    formId: "inspDefFormId",
    categoryId: "inspDefCategoryId",
    priorityId: "inspDefPriorityId",
    creationType: "inspDefCreationType",
    assignmentType: "inspDefAssignmentType"
  };
  for (const [k, id] of Object.entries(map)) {
    const el = document.getElementById(id);
    if (!el) continue;
    if (state.inspDefaults[k] != null && state.inspDefaults[k] !== "") el.value = state.inspDefaults[k];
  }
}

function saveInspDefaultsFromUi() {
  const grab = id => (document.getElementById(id)?.value || "").trim();
  const obj = {
    formId: grab("inspDefFormId"),
    categoryId: grab("inspDefCategoryId"),
    priorityId: grab("inspDefPriorityId"),
    creationType: grab("inspDefCreationType") || "2",
    assignmentType: grab("inspDefAssignmentType") || "5"
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
  const d = state.inspDefaults || {};
  if (!d.formId) errors.push("Defaults: Form ID is missing — fill the Defaults panel");
  if (!d.categoryId) errors.push("Defaults: Category ID is missing");
  if (!d.priorityId) errors.push("Defaults: Priority ID is missing");

  if (!row.name) errors.push("Name is required");
  if (!row.sites) errors.push("At least one Site is required");

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
    row._assignedToId = null;
    if (row.assignedTo) {
      row._assignedToId = await findInList("users", "users", row.assignedTo);
      if (!row._assignedToId) throw new Error(`Assigned-to user not found: ${row.assignedTo}`);
    }
    // Resource — use stated type, or fall back to first building, then first site.
    row._resourceId = null;
    if (row.resource) {
      const rt = (row.resourceType || "building").toLowerCase();
      const moduleName = rt === "asset" ? "asset"
                       : rt === "site" ? "site"
                       : rt === "floor" ? "floor"
                       : rt === "space" ? "space" : "building";
      row._resourceId = await portFindIdByName(moduleName, row.resource);
      if (!row._resourceId) throw new Error(`Resource "${row.resource}" not found in ${moduleName} module`);
    } else if (row._buildingIds.length) {
      row._resourceId = row._buildingIds[0];
    } else if (row._siteIds.length) {
      row._resourceId = row._siteIds[0];
    }
    if (!row._resourceId) errors.push("Resource is required (either fill the Resource column or provide at least one Building/Site)");
  } catch (e) {
    errors.push(e.message);
  }

  if (errors.length) { row.status = { kind:"error", text: errors.join("; ") }; return false; }
  row.status = { kind:"valid", text:"Valid" };
  return true;
}

function buildInspRecord(row) {
  const d = state.inspDefaults || {};
  return {
    creationType: Number(d.creationType || 2),
    siteId: null,
    sites: row._siteIds.map(id => ({ id })),
    buildings: row._buildingIds.map(id => ({ id })),
    assignmentType: Number(d.assignmentType || 5),
    assetCategory: null,
    spaceCategory: null,
    resource: row._resourceId ? { id: row._resourceId } : null,
    name: row.name,
    description: row.description || null,
    category: { id: Number(d.categoryId) },
    priority: { id: Number(d.priorityId) },
    assignedTo: row._assignedToId ? { id: row._assignedToId } : null,
    assignmentGroup: null,
    triggers: null,
    formId: Number(d.formId),
    actionFormId: Number(d.formId),
    mySignatureApplied: false
  };
}

async function importInspBatch(rows) {
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const rec = buildInspRecord(row);
    row.status = { kind:"running", text:"Creating template…" };
    renderInspQueue();
    let createdId = null;
    try {
      const r = await api("POST",
        "maintenance/api/v3/modules/inspectionTemplate",
        { moduleName: "inspectionTemplate", data: rec });
      const root = r?.data || {};
      const ret = root.inspectionTemplate || root.list || root.data || root;
      const arr = Array.isArray(ret) ? ret : (ret ? [ret] : []);
      createdId = arr[0]?.id || ret?.id || null;
      if (createdId) row._recordId = createdId;
    } catch (e) {
      let detail = e.message;
      if (e.body) {
        const msg = e.body.message || e.body.title || JSON.stringify(e.body);
        detail = String(msg).slice(0, 220);
      }
      row.status = { kind:"error", text: "Template create failed: " + detail };
      renderInspQueue();
      continue;
    }
    if (!createdId) {
      row.status = { kind:"error", text: "Template created but no ID returned" };
      renderInspQueue();
      continue;
    }
    // Auto-create default Q&A Page 1.
    row.status = { kind:"running", text:`Template ${createdId} created — adding Q&A page…` };
    renderInspQueue();
    try {
      const qa = await api("POST",
        "maintenance/api/v3/modules/qandaPage",
        { moduleName: "qandaPage", data: { name: "Page 1", description: "", parent: createdId, position: 1 } });
      const qaRoot = qa?.data || {};
      const qaRet = qaRoot.qandaPage || qaRoot.list || qaRoot.data || qaRoot;
      const qaArr = Array.isArray(qaRet) ? qaRet : (qaRet ? [qaRet] : []);
      const qaId = qaArr[0]?.id || qaRet?.id || null;
      if (qaId) row._qaPageId = qaId;
      row.status = { kind:"success", text:`Template ${createdId}` + (qaId ? ` + Page ${qaId}` : ` (Q&A page missing)`) };
    } catch (e) {
      row.status = { kind:"warn", text:`Template ${createdId} created, but Q&A page failed: ${e.message}` };
    }
    renderInspQueue();
  }
}

const INSP_HEADER_ALIASES = {
  "name": "name", "template name": "name", "inspection name": "name",
  "description": "description", "desc": "description",
  "site": "sites", "sites": "sites",
  "building": "buildings", "buildings": "buildings",
  "resource type": "resourceType",
  "resource": "resource", "resource name": "resource",
  "assigned to": "assignedTo", "assignee": "assignedTo"
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

(function wireInspectionTab(){
  if (!document.getElementById("inspGrid")) return;
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
    const headers = ["Name","Description","Sites","Buildings","Resource Type","Resource","Assigned To"];
    const sample = ["DPM Building Inspection Report","Routine monthly inspection","Investa HQ","Tower A","building","Tower A","mithun@example.com"];
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

JS_ANCHOR = """  $("#btnLogout").addEventListener("click", () => {"""


def main():
    if not INDEX.exists():
        fail(f"index.html not found at {INDEX}.")
    original = INDEX.read_text(encoding="utf-8")
    print(f"Read {INDEX} ({len(original):,} bytes)")

    # Block if v1 (sentinel from old script) is already applied.
    if "INSPECTIONS_PHASE1_APPLIED" in original:
        fail("v1 of the Inspections patch is already applied. Revert it first:\n"
             "  mv index.html.before-inspections-phase1.bak index.html\n"
             "Then re-run this script.")
    if "INSPECTIONS_PHASE1_V2_APPLIED" in original:
        fail("v2 already applied. Nothing to do.")
    if "tabInspections" in original:
        fail("An Inspections tab already exists in the HTML. Revert prior patches first.")

    text = original
    text = replace_once(text, TAB_BUTTON_OLD, TAB_BUTTON_NEW, "Tab button")
    text = replace_once(text, TAB_PANEL_ANCHOR, TAB_PANEL_REPLACEMENT, "Tab panel")
    text = replace_once(text, STATE_OLD, STATE_NEW, "State additions")
    text = replace_once(text, SWITCHTAB_OLD, SWITCHTAB_NEW, "switchTab branch")
    text = replace_once(text, JS_ANCHOR,
        "// INSPECTIONS_PHASE1_V2_APPLIED — payload matches captured UI POST.\n"
        + JS_MODULE + "\n  " + JS_ANCHOR,
        "JS module insertion")

    BACKUP.write_text(original, encoding="utf-8")
    INDEX.write_text(text, encoding="utf-8")
    delta = len(text) - len(original)
    print(f"\n✓ Inspections tab (Phase 1 v2) added.")
    print(f"  Backup: {BACKUP.name}")
    print(f"  New size: {len(text):,} bytes (delta: {delta:+,})")
    print()
    print("Restart `python3 start.py`, hard-refresh.")
    print()
    print("Defaults to set (from your DevTools capture):")
    print("  Form ID:          85375")
    print("  Category ID:      2347")
    print("  Priority ID:      1176")
    print("  Creation Type:    2  (already filled)")
    print("  Assignment Type:  5  (already filled)")
    print()
    print("Then add ONE row, Validate, Import. You should see two POSTs in the Logs:")
    print("  POST /modules/inspectionTemplate → returns template id")
    print("  POST /modules/qandaPage         → creates default Page 1")


if __name__ == "__main__":
    main()
