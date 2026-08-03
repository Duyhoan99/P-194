import { expect, test } from "@playwright/test";

const apiMode = process.env.PLAYWRIGHT_API_MODE ?? "real";
const traceId = "ops-trace-001";

test("operations and compliance views expose source posture and audit metadata only", async ({ page }) => {
  test.skip(apiMode !== "mock", "Requires a locally running API with synthetic operations state.");

  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/ops/clinical-status")) {
      return route.fulfill({
        json: {
          backend: "sqlite",
          database: { status: "CONFIGURED" },
          loaded_modules: ["overview", "laboratory"],
          source_profile: "synthetic-demo",
          ingestion: { checksum_status: "NOT_RECORDED", schema_status: "NOT_VALIDATED" },
          llm_gateway: { status: "UNAVAILABLE" },
          clinical_tools: { status: "AVAILABLE", count: 6 },
          latency: { query_timeout_ms: 2000 },
          trace_id: traceId,
        },
      });
    }
    if (path.endsWith("/ops/ingestion-runs")) {
      return route.fulfill({
        json: {
          runs: [
            {
              run_id: "synthetic-demo-bootstrap",
              dataset: "synthetic-demo",
              profile: "synthetic-demo",
              checksum_status: "NOT_RECORDED",
              schema_status: "NOT_VALIDATED",
              counts: { sources: 0, errors: 0 },
              errors: [],
            },
          ],
          trace_id: traceId,
        },
      });
    }
    if (path.endsWith("/admin/audit")) {
      return route.fulfill({
        json: {
          events: [
            {
              actor: "admin-1",
              action: "ASSIGN_CLINICAL_SUBJECT",
              subject_reference: "subject-102",
              timestamp: "2026-08-03T00:00:00Z",
              result: "SUCCESS",
              trace_id: traceId,
            },
          ],
          trace_id: traceId,
        },
      });
    }
    return route.fulfill({ status: 404, json: { detail: "Not found", trace_id: traceId } });
  });

  await page.goto("/operations");
  await expect(page.getByRole("heading", { name: "Clinical service posture" })).toBeVisible();
  await expect(page.getByText("synthetic-demo", { exact: true })).toBeVisible();
  await expect(page.getByText("overview, laboratory")).toBeVisible();
  await expect(page.locator("main")).not.toContainText("Creatinine");
  await expect(page.locator("main")).not.toContainText("1.2");

  await page.goto("/admin/audit");
  await expect(page.getByRole("heading", { name: "Append-only audit metadata" })).toBeVisible();
  await expect(page.getByText("ASSIGN_CLINICAL_SUBJECT")).toBeVisible();
  await expect(page.getByText("subject-102")).toBeVisible();
  await expect(page.locator("main")).not.toContainText("Clinical summary text");
});
