import { expect, test } from "@playwright/test";

const apiMode = process.env.PLAYWRIGHT_API_MODE ?? "real";
const traceId = "admin-trace-001";

const clinicalResponse = (records: unknown[]) => ({
  status: "SUCCESS",
  records,
  warnings: [],
  limitations: [],
  trace_id: traceId,
  page: { next_cursor: null, has_more: false },
});

test("admin assignment changes are reflected in the signed-in doctor dashboard", async ({ page }) => {
  test.skip(apiMode !== "mock", "Requires a locally running API with mutable synthetic demo state.");

  let doctorTwoAssignments: number[] = [];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const doctorTwo = {
      user_id: "doctor-2",
      role: "DOCTOR",
      state: "ACTIVE",
      assignments: doctorTwoAssignments.map((subjectId) => `subject-${subjectId}`),
      assignment_history: [],
    };

    if (path.endsWith("/auth/demo-login")) return route.fulfill({ status: 204 });
    if (path.endsWith("/admin/users") && request.method() === "GET") {
      return route.fulfill({ json: { users: [doctorTwo], trace_id: traceId } });
    }
    if (path.endsWith("/admin/users/doctor-2/assignments") && request.method() === "POST") {
      doctorTwoAssignments = [102];
      return route.fulfill({ json: doctorTwo });
    }
    if (path.endsWith("/admin/users/doctor-2/assignments/102") && request.method() === "DELETE") {
      doctorTwoAssignments = [];
      return route.fulfill({ json: doctorTwo });
    }
    if (path.endsWith("/clinical/patients")) {
      return route.fulfill({ json: { patients: doctorTwoAssignments, trace_id: traceId } });
    }
    if (path.endsWith("/clinical/patients/102")) {
      return route.fulfill({
        json: clinicalResponse([
          {
            record_type: "patient",
            data: { anchor_age: 0, gender: "F" },
            lineage: { table: "patients", source_row_key: "subject_id=102" },
          },
        ]),
      });
    }
    if (path.endsWith("/clinical/patients/102/timeline") || path.endsWith("/clinical/patients/102/labs")) {
      return route.fulfill({ json: clinicalResponse([]) });
    }
    if (path.endsWith("/clinical/patients/102/summaries/current")) {
      return route.fulfill({ status: 404, json: { detail: "Not found", trace_id: traceId } });
    }
    return route.fulfill({ status: 404, json: { detail: "Not found", trace_id: traceId } });
  });

  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Operational accounts" })).toBeVisible();
  await expect(page.getByText("None recorded.")).toBeVisible();

  const grantStatus = await page.evaluate(async () => {
    const response = await fetch("/api/v1/admin/users/doctor-2/assignments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject_id: 102 }),
    });
    return response.status;
  });
  expect(grantStatus).toBe(200);

  await page.reload();
  await expect(page.getByText("subject-102")).toBeVisible();

  await page.goto("/");
  await page.getByLabel("Demo username").fill("doctor-2");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Assigned patients" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Subject 102" })).toBeVisible();

  const revokeStatus = await page.evaluate(async () => {
    const response = await fetch("/api/v1/admin/users/doctor-2/assignments/102", { method: "DELETE" });
    return response.status;
  });
  expect(revokeStatus).toBe(200);
});
