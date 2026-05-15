/**
 * Cloudflare Worker — Import Manager
 *
 * Two responsibilities:
 *   1. /proxy?url=...        — forwards browser requests to Facilio's API
 *                              (so browsers don't get blocked by CORS)
 *   2. /config/get | /config/set — KV-backed JSON storage for org-level
 *                                  admin settings (visible tabs, fields, etc.)
 *
 * Endpoints
 *   GET  /                   — friendly landing page (200 plain text)
 *   GET/POST/PATCH/PUT/DELETE /proxy?url=<Facilio API URL>
 *   GET  /config/get?key=<orgKey>
 *   POST /config/set?key=<orgKey>   body: JSON   header: x-admin-password
 *
 * Headers forwarded to Facilio:
 *   x-api-key, x-device-type, x-version, x-org-group, content-type
 *
 * KV setup (one-time, in Cloudflare dashboard):
 *   1. Workers & Pages → KV → Create a namespace named "IMPORT_MANAGER_KV"
 *   2. Back in your Worker → Settings → Variables → KV Namespace Bindings
 *   3. Add a binding:
 *        Variable name = IMPORT_MANAGER_KV
 *        KV namespace  = IMPORT_MANAGER_KV (the one created above)
 *   4. Save & Deploy the Worker
 *
 * Admin password is the same one used in the UI's Facilio Settings panel.
 */

const ALLOWED_HEADERS = [
  "x-api-key",
  "x-device-type",
  "x-version",
  "x-org-group",
  "x-admin-password",
  "content-type"
];

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, PATCH, PUT, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": ALLOWED_HEADERS.join(", "),
  "Access-Control-Max-Age": "86400"
};

// Match the password used in the UI (index.html → ADMIN_PASSWORD).
// Override via Worker env var ADMIN_PASSWORD in production.
const DEFAULT_ADMIN_PASSWORD = "Facilio1234!@#$";

function jsonResp(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", ...CORS_HEADERS }
  });
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
    }

    const url = new URL(request.url);

    // ── /config/get?key=<orgKey> ───────────────────────────────────────
    if (url.pathname === "/config/get") {
      const key = url.searchParams.get("key");
      if (!key) return jsonResp({ error: "Missing key parameter" }, 400);
      if (!env.IMPORT_MANAGER_KV) return jsonResp({ error: "KV namespace not bound — see Worker setup" }, 500);
      try {
        const raw = await env.IMPORT_MANAGER_KV.get(key);
        if (!raw) return new Response("null", {
          status: 200,
          headers: { "Content-Type": "application/json", ...CORS_HEADERS }
        });
        return new Response(raw, {
          status: 200,
          headers: { "Content-Type": "application/json", ...CORS_HEADERS }
        });
      } catch (e) {
        return jsonResp({ error: "KV read failed: " + e.message }, 500);
      }
    }

    // ── /config/set?key=<orgKey> ───────────────────────────────────────
    if (url.pathname === "/config/set") {
      if (!["POST", "PUT"].includes(request.method)) {
        return jsonResp({ error: "Method not allowed" }, 405);
      }
      const expectedPwd = (env.ADMIN_PASSWORD && env.ADMIN_PASSWORD.length > 0)
        ? env.ADMIN_PASSWORD : DEFAULT_ADMIN_PASSWORD;
      const pwd = request.headers.get("x-admin-password") || "";
      if (pwd !== expectedPwd) {
        return jsonResp({ error: "Unauthorized — bad x-admin-password" }, 401);
      }
      const key = url.searchParams.get("key");
      if (!key) return jsonResp({ error: "Missing key parameter" }, 400);
      if (!env.IMPORT_MANAGER_KV) return jsonResp({ error: "KV namespace not bound — see Worker setup" }, 500);
      const body = await request.text();
      // Validate JSON before storing
      try { JSON.parse(body); }
      catch (e) { return jsonResp({ error: "Invalid JSON body: " + e.message }, 400); }
      try {
        await env.IMPORT_MANAGER_KV.put(key, body);
        return jsonResp({ ok: true });
      } catch (e) {
        return jsonResp({ error: "KV write failed: " + e.message }, 500);
      }
    }

    // ── Landing page ───────────────────────────────────────────────────
    if (!url.pathname.startsWith("/proxy")) {
      return new Response(
        "Import Manager proxy is running.\n\n" +
        "Endpoints:\n" +
        "  /proxy?url=<Facilio API URL>           — forwards a Facilio API call\n" +
        "  /config/get?key=<orgKey>               — read admin settings JSON\n" +
        "  /config/set?key=<orgKey>               — write admin settings (POST, x-admin-password header)\n",
        { status: 200, headers: { "Content-Type": "text/plain", ...CORS_HEADERS } }
      );
    }

    // ── /proxy?url=... (unchanged from before) ─────────────────────────
    const target = url.searchParams.get("url");
    if (!target) {
      return new Response("Missing url query parameter", {
        status: 400, headers: CORS_HEADERS
      });
    }
    const headers = new Headers();
    for (const h of ALLOWED_HEADERS) {
      const v = request.headers.get(h);
      // Don't forward x-admin-password to Facilio
      if (v && h !== "x-admin-password") headers.set(h, v);
    }
    const init = {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer()
    };
    try {
      const upstream = await fetch(decodeURIComponent(target), init);
      const body = await upstream.arrayBuffer();
      const respHeaders = new Headers();
      const ct = upstream.headers.get("content-type");
      if (ct) respHeaders.set("Content-Type", ct);
      for (const [k, v] of Object.entries(CORS_HEADERS)) respHeaders.set(k, v);
      return new Response(body, { status: upstream.status, headers: respHeaders });
    } catch (e) {
      return new Response("Upstream fetch failed: " + e.message, {
        status: 502, headers: { "Content-Type": "text/plain", ...CORS_HEADERS }
      });
    }
  }
};
