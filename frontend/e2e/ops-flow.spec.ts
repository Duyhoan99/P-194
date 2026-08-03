import { expect, type Page, test } from "@playwright/test";

import { containsOnlyOperationalMetadata, forbiddenClinicalFields } from "./operationalSafety";

const apiMode = process.env.PLAYWRIGHT_API_MODE ?? "real";
const apiUrl = apiMode === "mock" ? "" : process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";
const traceId = "ops-trace-001";

type BrowserResponse = { status: number; text: string };

function expectSafeOperationalMetadata(response: BrowserResponse) {
  expect(containsOnlyOperationalMetadata(response.text)).toBe(true);
}

async function expectSafeOperationalView(page: Page) {
  for (const field of forbiddenClinicalFields) {
    await expect(page.locator("main")).not.toContainText(new RegExp(field, "i"));
  }
}

async function browserRequest(page: Page, path: string, init: RequestInit = {}): Promise<BrowserResponse> {
  return page.evaluate(async ({ init, path, url }) => {
    const response = await fetch(`${url}${path}`, { ...init, credentials: "include" });
    return { status: response.status, text: await response.text() };
  }, { init, path, url: apiUrl });
}

async function realLogin(page: Page, username: string) {
  const response = await browserRequest(page, "/api/v1/auth/demo-login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password: "demo" }),
  });
  expect(response.status).toBe(204);
}

async function installRoleAwareMock(page: Page) {
  let actor: "ADMIN" | "COMPLIANCE" | "DATA_STEWARD" | "DOCTOR" | null = null;
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const forbidden = () => route.fulfill({ status: 403, json: { detail: "Permission denied", trace_id: traceId } });
    if (path.endsWith("/auth/demo-login") && request.method() === "POST") {
      const username = JSON.parse(request.postData() ?? "{}").username;
      actor = username === "admin-1" ? "ADMIN" : username === "compliance-1" ? "COMPLIANCE" : username === "steward-1" ? "DATA_STEWARD" : username === "doctor-1" ? "DOCTOR" : null;
      return actor ? route.fulfill({ status: 204 }) : forbidden();
    }
    if (path.endsWith("/ops/clinical-status")) {
      return actor === "ADMIN" || actor === "DATA_STEWARD" ? route.fulfill({ json: { backend: "sqlite", database: { status: "CONFIGURED" }, loaded_modules: ["overview", "laboratory"], source_profile: "synthetic-demo", ingestion: { checksum_status: "NOT_RECORDED", schema_status: "NOT_VALIDATED" }, llm_gateway: { status: "UNAVAILABLE" }, clinical_tools: { status: "AVAILABLE", count: 6 }, latency: { query_timeout_ms: 2000 }, trace_id: traceId } }) : forbidden();
    }
    if (path.endsWith("/ops/ingestion-runs")) {
      return actor === "ADMIN" || actor === "DATA_STEWARD" ? route.fulfill({ json: { runs: [{ run_id: "synthetic-demo-bootstrap", dataset: "synthetic-demo", profile: "synthetic-demo", checksum_status: "NOT_RECORDED", schema_status: "NOT_VALIDATED", counts: { sources: 0, errors: 0 }, errors: [] }], trace_id: traceId } }) : forbidden();
    }
    if (path.endsWith("/admin/audit")) {
      return actor === "ADMIN" || actor === "COMPLIANCE" ? route.fulfill({ json: { events: [{ actor: "admin-1", action: "ASSIGN_CLINICAL_SUBJECT", subject_reference: "subject-102", timestamp: "2026-08-03T00:00:00Z", result: "SUCCESS", trace_id: traceId }], trace_id: traceId } }) : forbidden();
    }
    return route.fulfill({ status: 404, json: { detail: "Not found", trace_id: traceId } });
  });
}

test("operations and compliance views require role-aware sessions and expose metadata only", async ({ page }) => {
  await page.goto("/");

  if (apiMode === "mock") {
    await installRoleAwareMock(page);

    const unauthenticated = await browserRequest(page, "/api/v1/ops/clinical-status");
    expect(unauthenticated.status).toBe(403);
    expectSafeOperationalMetadata(unauthenticated);

    await realLogin(page, "doctor-1");
    const doctorDenied = await browserRequest(page, "/api/v1/ops/clinical-status");
    expect(doctorDenied.status).toBe(403);
    expectSafeOperationalMetadata(doctorDenied);

    await realLogin(page, "steward-1");
    const status = await browserRequest(page, "/api/v1/ops/clinical-status");
    const ingestion = await browserRequest(page, "/api/v1/ops/ingestion-runs");
    expect(status.status).toBe(200);
    expect(ingestion.status).toBe(200);
    expectSafeOperationalMetadata(status);
    expectSafeOperationalMetadata(ingestion);
    await page.goto("/operations");
    await expect(page.getByRole("heading", { name: "Clinical service posture" })).toBeVisible();
    await expectSafeOperationalView(page);

    await realLogin(page, "compliance-1");
    const audit = await browserRequest(page, "/api/v1/admin/audit");
    const complianceDenied = await browserRequest(page, "/api/v1/ops/clinical-status");
    expect(audit.status).toBe(200);
    expect(complianceDenied.status).toBe(403);
    expectSafeOperationalMetadata(audit);
    expectSafeOperationalMetadata(complianceDenied);
    await page.goto("/admin/audit");
    await expect(page.getByRole("heading", { name: "Append-only audit metadata" })).toBeVisible();
    await expectSafeOperationalView(page);
    return;
  }

  expect(apiMode).toBe("real");
  await realLogin(page, "doctor-1");
  const doctorDenied = await browserRequest(page, "/api/v1/ops/clinical-status");
  expect(doctorDenied.status).toBe(403);
  expectSafeOperationalMetadata(doctorDenied);

  await realLogin(page, "steward-1");
  const status = await browserRequest(page, "/api/v1/ops/clinical-status");
  const ingestion = await browserRequest(page, "/api/v1/ops/ingestion-runs");
  expect(status.status).toBe(200);
  expect(ingestion.status).toBe(200);
  expectSafeOperationalMetadata(status);
  expectSafeOperationalMetadata(ingestion);

  await realLogin(page, "compliance-1");
  const audit = await browserRequest(page, "/api/v1/admin/audit");
  const complianceDenied = await browserRequest(page, "/api/v1/ops/clinical-status");
  expect(audit.status).toBe(200);
  expect(complianceDenied.status).toBe(403);
  expectSafeOperationalMetadata(audit);
  expectSafeOperationalMetadata(complianceDenied);
});
