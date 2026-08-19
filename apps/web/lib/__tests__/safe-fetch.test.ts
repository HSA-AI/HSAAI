/**
 * HSAAI Safe Fetch Utility — Unit Tests v3.0
 * ═══════════════════════════════════════════════════════════════════════
 *
 * Tests that verify:
 *   1. HTML responses are NEVER used as error messages
 *   2. JSON responses are parsed correctly
 *   3. Network errors return structured ApiError
 *   4. Timeouts return structured ApiError
 *   5. All HTTP status codes map to correct error codes
 *   6. Content-Type validation prevents HTML injection
 *   7. Request-ID is generated for every request
 *
 * ═══════════════════════════════════════════════════════════════════════
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { apiGet, apiPost, ErrorCodes } from "../safe-fetch";

// Mock global fetch
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

describe("Safe Fetch Utility", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should parse JSON response successfully", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ status: "ok", service: "test" }),
    });

    const result = await apiGet<{ status: string }>("/api/test");
    expect(result.error).toBeNull();
    expect(result.data).toEqual({ status: "ok", service: "test" });
    expect(result.status).toBe(200);
    expect(result.requestId).toMatch(/^req_/);
  });

  it("should NEVER use HTML response body as error message", async () => {
    const htmlBody = "<!DOCTYPE html><html><head><script>malicious</script></head></html>";
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      headers: new Headers({ "content-type": "text/html" }),
      text: async () => htmlBody,
      json: async () => { throw new Error("Not JSON"); },
    });

    const result = await apiGet("/api/nonexistent");

    expect(result.error).not.toBeNull();
    expect(result.error!.code).toBe(ErrorCodes.NOT_FOUND);
    // CRITICAL: The error message must NOT contain any HTML
    expect(result.error!.message).not.toContain("<!DOCTYPE");
    expect(result.error!.message).not.toContain("<html");
    expect(result.error!.message).not.toContain("<script");
    // The message should be the Arabic friendly message
    expect(result.error!.message).toContain("غير موجود");
  });

  it("should detect HTML response on 200 OK and return HTML_RESPONSE error", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "text/html" }),
      json: async () => { throw new Error("Not JSON"); },
      text: async () => "<!DOCTYPE html><html></html>",
    });

    const result = await apiGet("/api/test");

    expect(result.error).not.toBeNull();
    expect(result.error!.code).toBe(ErrorCodes.HTML_RESPONSE);
    expect(result.error!.message).not.toContain("<!DOCTYPE");
  });

  it("should handle 401 Unauthorized", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ detail: "Token expired" }),
      text: async () => '{"detail":"Token expired"}',
    });

    const result = await apiGet("/api/protected");

    expect(result.error!.code).toBe(ErrorCodes.UNAUTHORIZED);
    expect(result.error!.message).toContain("تسجيل الدخول");
  });

  it("should handle 403 Forbidden", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 403,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ detail: "Insufficient role" }),
      text: async () => '{"detail":"Insufficient role"}',
    });

    const result = await apiGet("/api/admin");

    expect(result.error!.code).toBe(ErrorCodes.FORBIDDEN);
    expect(result.error!.message).toContain("صلاحية");
  });

  it("should handle 500 Server Error", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ detail: "Internal server error" }),
      text: async () => '{"detail":"Internal server error"}',
    });

    const result = await apiGet("/api/test", { retries: 0 });

    expect(result.error!.code).toBe(ErrorCodes.SERVER_ERROR);
    expect(result.error!.message).toContain("خادم");
  });

  it("should handle 503 Service Unavailable", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 503,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ detail: "Service unavailable" }),
      text: async () => '{"detail":"Service unavailable"}',
    });

    const result = await apiGet("/api/test", { retries: 0 });

    expect(result.error!.code).toBe(ErrorCodes.SERVICE_UNAVAILABLE);
    expect(result.error!.message).toContain("غير متاحة");
  });

  it("should handle network errors (fetch throws TypeError)", async () => {
    mockFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const result = await apiGet("/api/test", { retries: 0 });

    expect(result.error!.code).toBe(ErrorCodes.NETWORK_ERROR);
    expect(result.error!.message).toContain("الاتصال");
    expect(result.error!.status).toBe(0);
  });

  it("should handle timeout (AbortError)", async () => {
    const abortError = new DOMException("The operation was aborted", "AbortError");
    mockFetch.mockRejectedValueOnce(abortError);

    const result = await apiGet("/api/test", { timeout: 100, retries: 0 });

    expect(result.error!.code).toBe(ErrorCodes.TIMEOUT);
    expect(result.error!.message).toContain("مهلة");
  });

  it("should handle invalid JSON response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => { throw new SyntaxError("Unexpected token <"); },
    });

    const result = await apiGet("/api/test");

    expect(result.error!.code).toBe(ErrorCodes.INVALID_JSON);
    expect(result.error!.message).toContain("غير صالحة");
  });

  it("should generate unique Request-ID for each request", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({}),
    });

    const result1 = await apiGet("/api/test");
    const result2 = await apiGet("/api/test");

    expect(result1.requestId).toMatch(/^req_/);
    expect(result2.requestId).toMatch(/^req_/);
    expect(result1.requestId).not.toBe(result2.requestId);
  });

  it("should send Accept: application/json header", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({}),
    });

    await apiGet("/api/test");

    const callArgs = mockFetch.mock.calls[0];
    const options = callArgs[1];
    expect(options.headers["Accept"]).toBe("application/json");
  });

  it("should send X-Request-ID header", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({}),
    });

    const result = await apiGet("/api/test");

    const callArgs = mockFetch.mock.calls[0];
    const options = callArgs[1];
    expect(options.headers["X-Request-ID"]).toBe(result.requestId);
  });

  it("should handle POST with body", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({ id: 1, name: "created" }),
    });

    const result = await apiPost("/api/create", { name: "test" });

    expect(result.data).toEqual({ id: 1, name: "created" });
    const callArgs = mockFetch.mock.calls[0];
    const options = callArgs[1];
    expect(options.method).toBe("POST");
    expect(options.body).toBe(JSON.stringify({ name: "test" }));
  });

  it("should truncate long error messages (defense in depth)", async () => {
    // Even if somehow a long string gets through, it should be truncated in ErrorCard
    // This test verifies the safeFetch doesn't include HTML in the detail
    const longHtml = "<!DOCTYPE html>" + "x".repeat(10000);
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      headers: new Headers({ "content-type": "text/html" }),
      text: async () => longHtml,
      json: async () => { throw new Error("Not JSON"); },
    });

    const result = await apiGet("/api/test");

    // The detail might contain a short note, but NOT the HTML body
    expect(result.error!.detail).not.toContain("<!DOCTYPE");
    expect(result.error!.detail).not.toContain("x".repeat(100));
  });
});
