#!/usr/bin/env python3
"""
apply_inspections_tab_phase1_v4.py

Phase 1 v4 — restores the fields v3 stripped (Facilio needs them) AND
adds the proper Scope / Scope Category UI from the user's screenshots.

What's new vs v3:
  - Defaults: Form ID (auto-discovered), Category ID, Priority ID,
    Assignment Type (default 5 for the Multiple-Building case).
  - Per-row: Scope (Single | Multiple), Resource Type (for Single),
    Scope Category (for Multiple — All Floors / All Spaces / Space Category
    / Asset Category / Current Asset / Meter Type), Scope Cat Name.
  - Payload now matches the captured UI POST EXACTLY:
      creationType (1 if Single else 2), siteId (id if Single else null),
      sites[], buildings[], assignmentType (defaults from panel, will be
      overridden per-row in a later patch once we know the mapping),
      assetCategory, spaceCategory, resource, name, description, category,
      priority, assignedTo, assignmentGroup:null, triggers:null,
      formId, actionFormId, mySignatureApplied:false.
  - Q&A Page 1 still auto-created.

Revert any prior v1/v2/v3 first, then run.
"""

import sys
from pathlib import Path

INDEX = Path(__file__).parent / "index.html"
BACKUP = Path(__file__).parent / "index.html.before-inspections-phase1-v4.bak"


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


TAB_BUTTON_OLD = """    <button class="tab" data-tab="portfolio">Portfolio</button>
    <button class="tab" data-tab="logs">Record History</button>"""
TAB_BUTTON_NEW = """    <button class="tab" data-tab="portfolio">Portfolio</button>
    <button class="tab" data-tab="inspections">Inspections</button>
    <button class="tab" data-tab="logs">Record History</button>"""

TAB_PANEL_NEW = """
  <!-- ===== Inspection Templates Tab ===== -->
  <div id="tabInspections" class="tab-panel hidden">
    <div class="panel" style="padding: 12px 14px;">
      <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">
        <div>
          <h3 style="margin:0 0 4px;">Inspection Templates</h3>
          <p class="muted small" style="margin:0;">Bulk-create inspection templates with proper Scope handling. A default Q&amp;A "Page 1" is auto-created for each template.</p>
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
        <summary>Defaults (Form ID auto-discovers; fill the rest from your DevTools capture)</summary>
        <div class="help-body">
          <div class="grid-3">
            <label class="field"><span class="lbl">Form ID *</span><input id="inspDefFormId" placeholder="(discovering…)" /></label>
            <label class="field"><span class="lbl">Category ID *</span><input id="inspDefCategoryId" placeholder="e.g. 2347" /></label>
            <label class="field"><span class="lbl">Priority ID *</span><input id="inspDefPriorityId" placeholder="e.g. 1176" /></label>
            <label class="field"><span class="lbl">Default Assignment Type</span><input id="inspDefAssignmentType" value="5" /></label>
          </div>
          <p class="muted small" style="margin:6px 0 0;">Per-row Scope (Single/Multiple) auto-sets <code>creationType</code> (1 or 2). The Default Assignment Type above is used unless a row's Scope Category mapping overrides it (we'll expand the mapping table as we capture more UI POSTs from your account).</p>
          <div class="card-actions" style="margin-top:4px;">
            <button class="btn ghost" id="btnInspDiscover">Re-discover Form ID</button>
            <button class="btn ghost" id="btnInspDefaultsSave">Save defaults</button>
            <span class="muted small" id="inspDefaultsStatus"></span>
          </div>
        </div>
      </details>

      <details class="help" style="margin-top: 6px;">
        <summary>Paste rows from Excel</summary>
        <div class="help-body">
          Recognised columns: Name, Description, Scope, Sites, Buildings, Resource Type, Resource, Scope Category, Scope Cat Name, Assigned To.
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
  // Inspection Templates queue (Phase 1 v4 — Scope-aware payload)
  inspQueue: [],
  inspDefaults: null,"""

SWITCHTAB_OLD = """  $("#tabPortfolio")?.classList.toggle("hidden", name !== "portfolio");
  $("#tabLogs")?.classList.toggle("hidden", name !== "logs");"""
SWITCHTAB_NEW = """  $("#tabPortfolio")?.classList.toggle("hidden", name !== "portfolio");
  $("#tabInspections")?.classList.toggle("hidden", name !== "inspections");
  $("#tabLogs")?.classList.toggle("hidden", name !== "logs");
  if (name === "inspections") { try { autoDiscoverInspectionForm(); } catch (_) {} }"""

JS_MODULE = """
// ---------- Inspection Templates (Phase 1 v4: Scope-aware) ----------

const INSP_DEFAULTS_LS_KEY = "ppm-manager.inspections.defaults.v4";

const INSP_COLUMN_DEFS = [
  { key:"_num",        label:"#",              kind:"num",     width:"w-num",    sticky:true },
  { key:"_status",     label:"Status",         kind:"status",  width:"w-status", sticky:true },
  { key:"name",        label:"Name *",         kind:"text",    width:"w-md" },
  { key:"description", label:"Description",    kind:"text",    width:"w-lg" },
  { key:"scope",       label:"Scope *",        kind:"select",  width:"w-sm",
    options:[{v:"single",l:"Single"},{v:"multiple",l:"Multiple"}] },
  { key:"sites",       label:"Sites *",        kind:"text",    width:"w-md", picklist:"site",
    placeholder:"one for Single, comma-sep for Multiple" },
  { key:"buildings",   label:"Buildings",      kind:"text",    width:"w-md", picklist:"building",
    placeholder:"only for Multiple" },
  { key:"resourceType",label:"Resource Type",  kind:"select",  width:"w-sm",
    options:[{v:"",l:""},{v:"asset",l:"Asset"},{v:"site",l:"Site"},{v:"building",l:"Building"},{v:"floor",l:"Floor"},{v:"space",l:"Space"}],
    placeholder:"only for Single" },
  { key:"resource",    label:"Resource",       kind:"text",    width:"w-md",
    placeholder:"only for Single" },
  { key:"scopeCategory", label:"Scope Category", kind:"select", width:"w-md",
    options:[{v:"",l:""},{v:"all_floors",l:"All Floors"},{v:"all_spaces",l:"All Spaces"},{v:"space_category",l:"Space Category"},{v:"asset_category",l:"Asset Category"},{v:"current_asset",l:"Current Asset"},{v:"meter_type",l:"Meter Type"}],
    placeholder:"only for Multiple" },
  { key:"scopeCategoryName", label:"Scope Cat Name", kind:"text", width:"w-md", picklist:"scopeCategory",
    placeholder:"for Space/Asset Category" },
  { key:"assignedTo",  label:"Assigned To",    kind:"text",    width:"w-md", picklist:"users" },
  { key:"_recordId",   label:"Record ID",      kind:"readonly",width:"w-sm" },
  { key:"_qaPageId",   label:"Q&A Page ID",    kind:"readonly",width:"w-sm" },
  { key:"_actions",    label:"",               kind:"actions", width:"w-actions" }
];

function blankInspRow() {
  return {
    name:"", description:"",
    scope:"multiple",
    sites:"", buildings:"",
    resourceType:"", resource:"",
    scopeCategory:"", scopeCategoryName:"",
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
  const fld = id => document.getElementById(id);
  if (fld("inspDefFormId") && state.inspDefaults.formId) fld("inspDefFormId").value = state.inspDefaults.formId;
  if (fld("inspDefCategoryId") && state.inspDefaults.categoryId) fld("inspDefCategoryId").value = state.inspDefaults.categoryId;
  if (fld("inspDefPriorityId") && state.inspDefaults.priorityId) fld("inspDefPriorityId").value = state.inspDefaults.priorityId;
  if (fld("inspDefAssignmentType") && state.inspDefaults.assignmentType) fld("inspDefAssignmentType").value = state.inspDefaults.assignmentType;
}

function saveInspDefaultsFromUi() {
  const grab = id => (document.getElementById(id)?.value || "").trim();
  state.inspDefaults = {
    formId: grab("inspDefFormId"),
    categoryId: grab("inspDefCategoryId"),
    priorityId: grab("inspDefPriorityId"),
    assignmentType: grab("inspDefAssignmentType") || "5"
  };
  localStorage.setItem(INSP_DEFAULTS_LS_KEY, JSON.stringify(state.inspDefaults));
  const el = document.getElementById("inspDefaultsStatus");
  if (el) {
    el.textContent = "✓ saved";
    setTimeout(() => { if (el.textContent === "✓ saved") el.textContent = ""; }, 3000);
  }
}

async function autoDiscoverInspectionForm(force) {
  const fld = document.getElementById("inspDefFormId");
  if (!fld) return;
  if (!force && state.inspDefaults?.formId && fld.value) return;
  fld.placeholder = "(discovering…)";
  try {
    if (force) state.formsByModule.inspectionTemplate = null;
    const entry = await ensureModuleForms("inspectionTemplate");
    if (entry?.selectedFormId) {
      fld.value = entry.selectedFormId;
      state.inspDefaults = state.inspDefaults || {};
      state.inspDefaults.formId = String(entry.selectedFormId);
      localStorage.setItem(INSP_DEFAULTS_LS_KEY, JSON.stringify(state.inspDefaults));
      log(`inspectionTemplate form discovered: ${entry.selectedFormId}`, "ok");
    }
  } catch (_) {}
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
  if (!d.formId) errors.push("Defaults: Form ID is missing");
  if (!d.categoryId) errors.push("Defaults: Category ID is missing");
  if (!d.priorityId) errors.push("Defaults: Priority ID is missing");

  if (!row.name) errors.push("Name is required");
  if (!row.scope) errors.push("Scope is required (Single or Multiple)");
  if (!row.sites) errors.push("At least one Site is required");

  if (row.scope === "single" && !row.resource) {
    errors.push("Resource is required for Single scope");
  }
  if (row.scope === "single" && !row.resourceType) {
    errors.push("Resource Type is required for Single scope");
  }
  if (row.scope === "multiple" && (row.scopeCategory === "space_category" || row.scopeCategory === "asset_category") && !row.scopeCategoryName) {
    errors.push("Scope Cat Name is required when Scope Category is Space/Asset Category");
  }

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
    row._resourceId = null;
    if (row.scope === "single" && row.resource) {
      const rt = (row.resourceType || "building").toLowerCase();
      const moduleName = rt === "asset" ? "asset"
                       : rt === "site" ? "site"
                       : rt === "floor" ? "floor"
                       : rt === "space" ? "space" : "building";
      row._resourceId = await portFindIdByName(moduleName, row.resource);
      if (!row._resourceId) throw new Error(`Resource "${row.resource}" not found in ${moduleName} module`);
    } else if (row.scope === "multiple") {
      // Resource defaults to first building, then first site.
      if (row._buildingIds.length)    row._resourceId = row._buildingIds[0];
      else if (row._siteIds.length)   row._resourceId = row._siteIds[0];
    }
    // Resolve scope category name (asset / space category)
    row._assetCategoryId = null;
    row._spaceCategoryId = null;
    if (row.scopeCategory === "asset_category" && row.scopeCategoryName) {
      row._assetCategoryId = await findInList("assetCategory", "assetCategory", row.scopeCategoryName);
      if (!row._assetCategoryId) throw new Error(`Asset category "${row.scopeCategoryName}" not found`);
    } else if (row.scopeCategory === "space_category" && row.scopeCategoryName) {
      row._spaceCategoryId = await findInList("spaceCategory", "spaceCategory", row.scopeCategoryName);
      if (!row._spaceCategoryId) throw new Error(`Space category "${row.scopeCategoryName}" not found`);
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
  const isSingle = row.scope === "single";
  const out = {
    creationType: isSingle ? 1 : 2,
    siteId: isSingle && row._siteIds[0] ? row._siteIds[0] : null,
    sites: row._siteIds.map(id => ({ id })),
    buildings: row._buildingIds.map(id => ({ id })),
    assignmentType: Number(d.assignmentType || 5),
    assetCategory: row._assetCategoryId ? { id: row._assetCategoryId } : null,
    spaceCategory: row._spaceCategoryId ? { id: row._spaceCategoryId } : null,
    resource: row._resourceId ? { id: row._resourceId } : null,
    name: row.name,
    description: row.description || null,
    category: d.categoryId ? { id: Number(d.categoryId) } : null,
    priority: d.priorityId ? { id: Number(d.priorityId) } : null,
    assignedTo: row._assignedToId ? { id: row._assignedToId } : null,
    assignmentGroup: null,
    triggers: null,
    formId: Number(d.formId),
    actionFormId: Number(d.formId),
    mySignatureApplied: false
  };
  return out;
}

async function importInspBatch(rows) {
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const rec = buildInspRecord(row);
    log(`Inspection payload: ${JSON.stringify(rec)}`, "dim");
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
      log(`Template "${row.name}" failed — Facilio: ${detail}`, "err");
      renderInspQueue();
      continue;
    }
    if (!createdId) {
      row.status = { kind:"error", text: "Template created but no ID returned" };
      renderInspQueue();
      continue;
    }
    row.status = { kind:"running", text:`Template ${createdId} — adding Q&A page…` };
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
      row.status = { kind:"warn", text:`Template ${createdId} created, Q&A page failed: ${e.message}` };
    }
    renderInspQueue();
  }
}

const INSP_HEADER_ALIASES = {
  "name": "name", "template name": "name", "inspection name": "name",
  "description": "description", "desc": "description",
  "scope": "scope",
  "site": "sites", "sites": "sites",
  "building": "buildings", "buildings": "buildings",
  "resource type": "resourceType",
  "resource": "resource", "resource name": "resource",
  "scope category": "scopeCategory",
  "scope cat name": "scopeCategoryName", "scope category name": "scopeCategoryName",
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
  document.getElementById("btnInspDiscover")?.addEventListener("click", () => autoDiscoverInspectionForm(true));

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
    const headers = ["Name","Description","Scope","Sites","Buildings","Resource Type","Resource","Scope Category","Scope Cat Name","Assigned To"];
    const samples = [
      ["DPM Building Inspection","Monthly check","multiple","Investa HQ","Tower A","","","","","mithun@example.com"],
      ["Chiller Inspection","Quarterly","single","Investa HQ","","asset","CH-001","","","tech@example.com"]
    ];
    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.aoa_to_sheet([headers, ...samples]);
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

    for sentinel, version in [("INSPECTIONS_PHASE1_V4_APPLIED", "v4"),
                              ("INSPECTIONS_PHASE1_V3_APPLIED", "v3"),
                              ("INSPECTIONS_PHASE1_V2_APPLIED", "v2"),
                              ("INSPECTIONS_PHASE1_APPLIED", "v1")]:
        if sentinel in original:
            if version == "v4":
                fail("v4 already applied. Nothing to do.")
            fail(f"Inspections patch {version} is currently applied. Revert first:\n"
                 f"  mv index.html.before-inspections-phase1{('-' + version) if version != 'v1' else ''}.bak index.html")
    if "tabInspections" in original:
        fail("An Inspections tab already exists. Revert prior patches first.")

    text = original
    text = replace_once(text, TAB_BUTTON_OLD, TAB_BUTTON_NEW, "Tab button")
    text = replace_once(text, TAB_PANEL_ANCHOR, TAB_PANEL_REPLACEMENT, "Tab panel")
    text = replace_once(text, STATE_OLD, STATE_NEW, "State additions")
    text = replace_once(text, SWITCHTAB_OLD, SWITCHTAB_NEW, "switchTab branch")
    text = replace_once(text, JS_ANCHOR,
        "// INSPECTIONS_PHASE1_V4_APPLIED — Scope-aware payload matching UI capture.\n"
        + JS_MODULE + "\n  " + JS_ANCHOR,
        "JS module insertion")

    BACKUP.write_text(original, encoding="utf-8")
    INDEX.write_text(text, encoding="utf-8")
    delta = len(text) - len(original)
    print(f"\n✓ Inspections tab (Phase 1 v4) added.")
    print(f"  Backup: {BACKUP.name}")
    print(f"  New size: {len(text):,} bytes (delta: {delta:+,})")
    print()
    print("Setup:")
    print("  - Form ID auto-discovers when you open the tab.")
    print("  - Fill Category ID (2347), Priority ID (1176), Assignment Type (5)")
    print("    in the Defaults panel. Click Save.")
    print()
    print("First test row — match your captured payload exactly:")
    print("  Name: test Insp")
    print("  Scope: Multiple")
    print("  Sites: <name of site with ID 1864017>")
    print("  Buildings: <name of building with ID 1864018>")
    print("  Resource Type: (blank — Multiple uses first building automatically)")
    print("  Resource: (blank)")
    print("  Scope Category: (blank — your capture had assetCategory:null, spaceCategory:null)")
    print()
    print("Validate + Import. The payload sent should match your UI capture:")
    print("  creationType:2, assignmentType:5, sites:[{id:1864017}], buildings:[{id:1864018}],")
    print("  category:{id:2347}, priority:{id:1176}, resource:{id:<first building id>},")
    print("  formId+actionFormId:<discovered>, mySignatureApplied:false, plus the nulls.")


if __name__ == "__main__":
    main()
