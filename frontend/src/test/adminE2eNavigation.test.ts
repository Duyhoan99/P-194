import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const adminFlowSource = readFileSync(
  resolve(process.cwd(), "e2e", "admin-flow.spec.ts"),
  "utf8",
);

describe("admin E2E mock flow navigation", () => {
  it("returns to the DoctorApp root before using its login controls", () => {
    const adminNavigation = adminFlowSource.indexOf('await page.goto("/admin");');
    const rootNavigation = adminFlowSource.indexOf(
      'await page.goto("/");',
      adminNavigation + 1,
    );
    const usernameInput = adminFlowSource.indexOf(
      'page.getByLabel("Demo username")',
      adminNavigation,
    );

    expect(adminNavigation).toBeGreaterThanOrEqual(0);
    expect(rootNavigation).toBeGreaterThan(adminNavigation);
    expect(rootNavigation).toBeLessThan(usernameInput);
  });
});
