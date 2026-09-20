/**
 * HSAAI RAG Service (v2.0 — No localStorage tokens)
 *
 * SECURITY FIX v2.0:
 *   - Removed authHeaders() that read token from window.localStorage (XSS leak risk).
 *   - Now uses the shared `api` axios client from services/api.ts which sends
 *     httpOnly cookies automatically via withCredentials: true.
 *   - Tenant ID and workspace ID are sourced server-side from JWT claims.
 *
 * FIX FIX-MEDIUM-QUALITY (Issue 8): replaced raw fetch() with the shared `api`
 * axios client for consistent error handling + 401→login redirect. The streaming
 * endpoint still uses fetch() because axios's XHR adapter cannot consume SSE
 * chunks in the browser; we route it through api's baseURL for URL consistency.
 */
import api from "./api";

export async function uploadKnowledgeDocument(
  file: File,
  tenantId = "default",
  workspaceId = "default",
  options: {
    visibility?: "workspace" | "public" | "restricted";
    allowedRoles?: string;
    allowedUsers?: string;
    classification?: string;
    tags?: string;
  } = {},
) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("tenant_id", tenantId);
  formData.append("workspace_id", workspaceId);
  formData.append("visibility", options.visibility || "workspace");
  formData.append("allowed_roles", options.allowedRoles || "");
  formData.append("allowed_users", options.allowedUsers || "");
  formData.append("classification", options.classification || "internal");
  formData.append("tags", options.tags || "");

  // FIX FIX-MEDIUM-QUALITY (Issue 8): use shared axios client so 401 redirects
  // to /login and error handling is consistent with the rest of the app.
  // Axios sets the multipart/form-data boundary automatically when given FormData.
  const res = await api.post(`/v1/rag/documents/upload`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export const uploadKnowledge = uploadKnowledgeDocument;

export async function searchKnowledge(
  query: string,
  tenantId = "default",
  workspaceId = "default",
  topK = 8,
  mode: "semantic" | "lexical" | "hybrid" = "hybrid",
) {
  const res = await api.post(`/v1/rag/search`, {
    query,
    tenant_id: tenantId,
    workspace_id: workspaceId,
    top_k: topK,
    mode,
  });
  return res.data;
}

export async function answerKnowledge(
  query: string,
  tenantId = "default",
  workspaceId = "default",
  topK = 6,
) {
  const res = await api.post(`/v1/rag/answer`, {
    query,
    tenant_id: tenantId,
    workspace_id: workspaceId,
    top_k: topK,
    mode: "hybrid",
    cite_sources: true,
  });
  return res.data;
}

export async function highlightKnowledge(
  query: string,
  tenantId = "default",
  workspaceId = "default",
  topK = 6,
) {
  const res = await api.post(`/v1/rag/highlight`, {
    query,
    tenant_id: tenantId,
    workspace_id: workspaceId,
    top_k: topK,
    mode: "hybrid",
  });
  return res.data;
}

export async function streamKnowledgeAnswer(
  query: string,
  onToken: (token: string) => void,
  onMetadata?: (metadata: unknown) => void,
  tenantId = "default",
  workspaceId = "default",
) {
  // FIX FIX-MEDIUM-QUALITY (Issue 8): use api.defaults.baseURL so this stream
  // endpoint uses the same origin/env config as the rest of the app. fetch is
  // still required here because axios's XHR adapter cannot consume SSE chunks
  // in the browser. The api request interceptor's X-Requested-With header is
  // added manually below for parity.
  const streamUrl = `${api.defaults.baseURL}/v1/rag/answer/stream`;
  const res = await fetch(streamUrl, {
    method: "POST",
    credentials: "include", // httpOnly cookie
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
    },
    body: JSON.stringify({
      query,
      tenant_id: tenantId,
      workspace_id: workspaceId,
      top_k: 6,
      mode: "hybrid",
    }),
  });
  if (!res.ok || !res.body) throw new Error(`RAG stream failed: ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";
    for (const event of events) {
      const dataLine = event.split("\n").find((line) => line.startsWith("data: "));
      if (!dataLine) continue;
      try {
        const data = JSON.parse(dataLine.slice(6));
        if (typeof data.token === "string") onToken(data.token);
        else if (data.sources || data.features) onMetadata?.(data);
      } catch {
        // Ignore malformed SSE chunks.
      }
    }
  }
}

export async function listKnowledgeDocuments(
  tenantId = "default",
  workspaceId = "default",
  limit = 50,
) {
  const res = await api.post(`/v1/rag/documents`, {
    tenant_id: tenantId,
    workspace_id: workspaceId,
    limit,
  });
  return res.data;
}

export async function deleteKnowledgeDocument(
  docId: string,
  tenantId = "default",
  workspaceId = "default",
) {
  const params = new URLSearchParams({ tenant_id: tenantId, workspace_id: workspaceId });
  const res = await api.delete(`/v1/rag/documents/${docId}?${params}`);
  return res.data;
}

export async function getKnowledgeAnalytics(
  tenantId = "default",
  workspaceId = "default",
) {
  const res = await api.post(`/v1/rag/analytics`, {
    tenant_id: tenantId,
    workspace_id: workspaceId,
  });
  return res.data;
}
