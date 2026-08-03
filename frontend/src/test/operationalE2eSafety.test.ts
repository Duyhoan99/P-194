import { describe, expect, it } from "vitest";

import { containsOnlyOperationalMetadata } from "../../e2e/operationalSafety";

describe("operational E2E safety", () => {
  it("accepts actor, action, result, status, count, trace, and source-table metadata", () => {
    expect(
      containsOnlyOperationalMetadata(
        JSON.stringify({ actor: "admin-1", action: "ASSIGN_CLINICAL_SUBJECT", result: "SUCCESS", count: 1, trace_id: "trace-1", table: "labevents" }),
      ),
    ).toBe(true);
  });

  it("rejects a clinical field name even when no value is present", () => {
    expect(containsOnlyOperationalMetadata('{"source_row_key":null}')).toBe(false);
  });
});
