import { expect, test } from "@playwright/test";

const apiMode = process.env.PLAYWRIGHT_API_MODE ?? "real";

const summaryId = "7c224337-2b0f-4f95-9e84-41e96df151d1";
const traceId = "4cc2bfc1-c299-4d85-955e-eb72f46c1058";
const lineage = { dataset: "synthetic-demo", version: "1", module: "hosp", table: "labevents", source_row_key: "labevent_id=9001", subject_id: 101, hadm_id: 201 };
const patient = { record_type: "patient", data: { anchor_age: 63, gender: "F" }, lineage: { ...lineage, table: "patients", source_row_key: "subject_id=101" } };
const admission = { record_type: "admission", data: {}, lineage: { ...lineage, table: "admissions", source_row_key: "hadm_id=201" } };
const lab = { record_type: "lab", data: { label: "Creatinine", valuenum: 1.2, valueuom: "mg/dL" }, lineage };
const clinicalResponse = (records: unknown[]) => ({ status: "SUCCESS", records, warnings: [], limitations: [], trace_id: traceId, page: { next_cursor: null, has_more: false } });
const version = (status: "DRAFT" | "NEEDS_REVISION" | "APPROVED") => ({
  summary_id: summaryId, version_id: "f4d6e6bb-f827-4b71-8804-c5d20b2df5c4", version_number: status === "DRAFT" ? 1 : 2, status, actor_id: "doctor-1", reason: null, created_at: "2026-08-03T00:00:00Z",
  draft: { summary_id: summaryId, subject_id: 101, hadm_id: null, stay_id: null, status, sections: { "Laboratory Trends": [{ claim_id: "claim-lab-1", section: "Laboratory Trends", text: "Creatinine: 1.2 mg/dL.", citation_ids: ["labevent_id=9001"], status: "VALID" }] }, citations: [{ citation_id: "labevent_id=9001", lineage, supported_fields: ["valuenum", "valueuom"] }], conflicts: [], warnings: [], limitations: ["This draft is generated from supplied evidence only and requires clinician review."], trace_id: traceId },
});

test("doctor completes the assigned-subject review flow and sees denied access for subject 102", async ({ page }) => {
  if (apiMode !== "mock") {
    test.info().annotations.push({ type: "api-mode", description: "real" });
  }

  if (apiMode !== "mock") {
    await page.goto("/");
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.getByRole("button", { name: "Open workspace" }).click();
    await page.getByRole("button", { name: /Generate draft|Request regeneration/ }).click();
    await page.getByRole("button", { name: /labevent_id=9001/ }).click();
    await expect(page.getByRole("complementary", { name: "Source record" })).toContainText("labevents");
    await page.getByLabelText(/Edit claim/).first().fill("Creatinine trended down to 1.0 mg/dL.");
    await page.getByRole("button", { name: "Revalidate and save draft" }).click();
    await page.getByRole("button", { name: "Approve" }).click();
    await page.getByLabelText("I reviewed the summary").check();
    await page.getByLabelText("I checked critical evidence").check();
    await page.getByLabelText("I understand AI is decision support only").check();
    await page.getByLabelText("I confirm my edits").check();
    await page.getByRole("dialog").getByRole("button", { name: "Approve" }).click();
    await expect(page.getByText("APPROVED", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "← Assigned patients" }).click();
    await page.getByLabelText("Verify server access for a subject ID").fill("102");
    await page.getByRole("button", { name: "Check access" }).click();
    await expect(page.getByRole("alert")).toContainText("Access to subject 102 is denied");
    await expect(page.evaluate(() => window.localStorage.length)).resolves.toBe(0);
    return;
  }

  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/demo-login")) return route.fulfill({ status: 204 });
    if (path.endsWith("/clinical/patients")) return route.fulfill({ json: { patients: [101], trace_id: traceId } });
    if (path.includes("/patients/102")) return route.fulfill({ status: 403, json: { detail: "Access to the requested clinical subject is denied.", trace_id: traceId } });
    if (path.endsWith("/clinical/patients/101")) return route.fulfill({ json: clinicalResponse([patient, admission]) });
    if (path.endsWith("/clinical/patients/101/timeline")) return route.fulfill({ json: clinicalResponse([admission]) });
    if (path.endsWith("/clinical/patients/101/labs")) return route.fulfill({ json: clinicalResponse([lab]) });
    if (path.endsWith("/clinical/patients/101/summaries/current")) return route.fulfill({ json: version("DRAFT") });
    if (path.endsWith("/clinical/patients/101/summaries")) return route.fulfill({ status: 201, json: version("DRAFT") });
    if (path.endsWith(`/clinical/summaries/${summaryId}`) && route.request().method() === "PATCH") return route.fulfill({ json: version("NEEDS_REVISION") });
    if (path.endsWith(`/clinical/summaries/${summaryId}/approve`)) return route.fulfill({ json: version("APPROVED") });
    return route.fulfill({ status: 404, json: { detail: "Not found", trace_id: traceId } });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("button", { name: "Open workspace" }).click();
  await page.getByRole("button", { name: "Request regeneration" }).click();
  await page.getByRole("button", { name: "labevent_id=9001" }).click();
  await expect(page.getByRole("complementary", { name: "Source record" })).toContainText("labevents");
  await page.getByLabelText("Edit claim-lab-1").fill("Creatinine trended down to 1.0 mg/dL.");
  await page.getByRole("button", { name: "Revalidate and save draft" }).click();
  await page.getByRole("button", { name: "Approve" }).click();
  await page.getByLabelText("I reviewed the summary").check();
  await page.getByLabelText("I checked critical evidence").check();
  await page.getByLabelText("I understand AI is decision support only").check();
  await page.getByLabelText("I confirm my edits").check();
  await page.getByRole("dialog").getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("APPROVED", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "← Assigned patients" }).click();
  await page.getByLabelText("Verify server access for a subject ID").fill("102");
  await page.getByRole("button", { name: "Check access" }).click();
  await expect(page.getByRole("alert")).toContainText("Access to subject 102 is denied");
  await expect(page.evaluate(() => window.localStorage.length)).resolves.toBe(0);
});
