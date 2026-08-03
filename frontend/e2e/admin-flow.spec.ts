import { expect, type Page, test } from "@playwright/test";

import { containsOnlyOperationalMetadata, forbiddenClinicalFields } from "./operationalSafety";

const apiMode = process.env.PLAYWRIGHT_API_MODE ?? "real";
const apiUrl = apiMode === "mock" ? "" : process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";
const traceId = "admin-trace-001";

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
  let actor: "ADMIN" | "DOCTOR" | null = null;
  let doctorTwoAssignments: number[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const forbidden = () => route.fulfill({ status: 403, json: { detail: "Permission denied", trace_id: traceId } });
    const doctorTwo = {
      user_id: "doctor-2",
      role: "DOCTOR",
      state: "ACTIVE",
      assignments: doctorTwoAssignments.map((subjectId) => `subject-${subjectId}`),
      assignment_history: [],
    };

    if (path.endsWith("/auth/demo-login") && request.method() === "POST") {
      const username = JSON.parse(request.postData() ?? "{}").username;
      actor = username === "admin-1" ? "ADMIN" : username === "doctor-1" || username === "doctor-2" ? "DOCTOR" : null;
      return actor ? route.fulfill({ status: 204 }) : forbidden();
    }
    if (path.endsWith("/admin/users") && request.method() === "GET") {
      return actor === "ADMIN" ? route.fulfill({ json: { users: [doctorTwo], trace_id: traceId } }) : forbidden();
    }
    if (path.endsWith("/admin/users/doctor-2/assignments") && request.method() === "POST") {
      if (actor !== "ADMIN") return forbidden();
      doctorTwoAssignments = [102];
      return route.fulfill({ json: doctorTwo });
    }
    if (path.endsWith("/admin/users/doctor-2/assignments/102") && request.method() === "DELETE") {
      if (actor !== "ADMIN") return forbidden();
      doctorTwoAssignments = [];
      return route.fulfill({ json: doctorTwo });
    }
    if (path.endsWith("/clinical/patients")) {
      return actor === "DOCTOR" ? route.fulfill({ json: { patients: doctorTwoAssignments, trace_id: traceId } }) : forbidden();
    }
    if (path.includes("/clinical/patients/102")) {
      if (actor !== "DOCTOR") return forbidden();
      if (path.endsWith("/summaries/current")) return route.fulfill({ status: 404, json: { detail: "Not found", trace_id: traceId } });
      return route.fulfill({ json: { status: "SUCCESS", records: [], warnings: [], limitations: [], trace_id: traceId, page: { next_cursor: null, has_more: false } } });
    }
    return route.fulfill({ status: 404, json: { detail: "Not found", trace_id: traceId } });
  });
}

test("admin assignment changes require an admin session and affect the doctor dashboard", async ({ page }) => {
  await page.goto("/");

  if (apiMode === "mock") {
    await installRoleAwareMock(page);

    const unauthenticated = await browserRequest(page, "/api/v1/admin/users");
    expect(unauthenticated.status).toBe(403);
    expectSafeOperationalMetadata(unauthenticated);

    await realLogin(page, "doctor-1");
    const doctorDenied = await browserRequest(page, "/api/v1/admin/users");
    expect(doctorDenied.status).toBe(403);
    expectSafeOperationalMetadata(doctorDenied);

    await realLogin(page, "admin-1");
    const granted = await browserRequest(page, "/api/v1/admin/users/doctor-2/assignments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject_id: 102 }),
    });
    expect(granted.status).toBe(200);
    expectSafeOperationalMetadata(granted);

    await page.goto("/admin");
    await expect(page.getByText("subject-102")).toBeVisible();
    await expectSafeOperationalView(page);

    await page.getByLabel("Demo username").fill("doctor-2");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("heading", { name: "Subject 102" })).toBeVisible();

    await realLogin(page, "admin-1");
    const revoked = await browserRequest(page, "/api/v1/admin/users/doctor-2/assignments/102", { method: "DELETE" });
    expect(revoked.status).toBe(200);
    expectSafeOperationalMetadata(revoked);
    return;
  }

  expect(apiMode).toBe("real");
  await realLogin(page, "doctor-1");
  const doctorDenied = await browserRequest(page, "/api/v1/admin/users");
  expect(doctorDenied.status).toBe(403);
  expectSafeOperationalMetadata(doctorDenied);

  await realLogin(page, "admin-1");
  const listedUsers = await browserRequest(page, "/api/v1/admin/users");
  expect(listedUsers.status).toBe(200);
  expectSafeOperationalMetadata(listedUsers);

  let granted = false;
  try {
    const assignment = await browserRequest(page, "/api/v1/admin/users/doctor-2/assignments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject_id: 102 }),
    });
    expect(assignment.status).toBe(200);
    expectSafeOperationalMetadata(assignment);
    granted = true;

    await realLogin(page, "doctor-2");
    const assignedPatients = await browserRequest(page, "/api/v1/clinical/patients");
    expect(assignedPatients.status).toBe(200);
    expect(assignedPatients.text).toContain("102");
    expectSafeOperationalMetadata(assignedPatients);
  } finally {
    if (granted) {
      await realLogin(page, "admin-1");
      const revoked = await browserRequest(page, "/api/v1/admin/users/doctor-2/assignments/102", { method: "DELETE" });
      expect(revoked.status).toBe(200);
      expectSafeOperationalMetadata(revoked);
    }
  }
});
