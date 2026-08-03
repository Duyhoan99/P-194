import type { ClinicalSummaryDraft, PatientWorkspace } from "@/lib/types";

export const draftSummary: ClinicalSummaryDraft = {
  summaryId: "7c224337-2b0f-4f95-9e84-41e96df151d1",
  subjectId: 101,
  status: "DRAFT",
  sections: {
    "Laboratory Trends": [
      {
        claimId: "claim-lab-1",
        section: "Laboratory Trends",
        text: "Creatinine recorded as 1.2 mg/dL.",
        citationIds: ["labevent_id=9001"],
        status: "VALID",
      },
    ],
  },
  citations: [
    {
      citationId: "labevent_id=9001",
      lineage: {
        dataset: "synthetic-demo",
        version: "1",
        module: "hosp",
        table: "labevents",
        sourceRowKey: "labevent_id=9001",
        subjectId: 101,
      },
      supportedFields: ["valuenum", "valueuom"],
    },
  ],
  conflicts: [
    {
      conflictId: "medication-source-conflict",
      topic: "Medication source status",
      evidenceIds: ["prescription_id=100", "emar_id=200"],
      status: "UNRESOLVED",
      resolutionNote: null,
    },
  ],
  warnings: ["Medication evidence is partial."],
  limitations: ["This is decision support only and requires clinician review."],
  traceId: "4cc2bfc1-c299-4d85-955e-eb72f46c1058",
};

export const patientWorkspace: PatientWorkspace = {
  patient: {
    subjectId: 101,
    anchorAge: 63,
    gender: "F",
    admissionCount: 1,
    icuStayCount: 1,
    summaryStatus: "DRAFT",
  },
  availability: "PARTIAL",
  timeline: [],
  summary: draftSummary,
  warnings: draftSummary.warnings,
  limitations: draftSummary.limitations,
};
