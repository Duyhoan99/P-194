import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { PatientWorkspace } from "@/components/PatientWorkspace";
import { patientWorkspace } from "@/test/fixtures";

it("opens a citation source panel without putting clinical data in the URL", async () => {
  const user = userEvent.setup();
  render(<PatientWorkspace workspace={patientWorkspace} onSave={async () => {}} onApprove={async () => {}} />);

  await user.click(screen.getByRole("button", { name: "labevent_id=9001" }));

  expect(screen.getByRole("complementary", { name: "Source record" })).toHaveTextContent("labevents");
  expect(window.location.search).toBe("");
});

it("shows partial-data warnings, limitations, and the decision support disclaimer", () => {
  render(<PatientWorkspace workspace={patientWorkspace} onSave={async () => {}} onApprove={async () => {}} />);

  expect(screen.getByText("Medication evidence is partial.")).toBeInTheDocument();
  expect(screen.getAllByText(/decision support only/i)).not.toHaveLength(0);
  expect(screen.getByText(/Medication source status/)).toBeInTheDocument();
});

it("reports an unavailable citation instead of silently hiding the missing source", async () => {
  const user = userEvent.setup();
  const workspaceWithUnavailableCitation = {
    ...patientWorkspace,
    summary: {
      ...patientWorkspace.summary!,
      citations: [],
      sections: {
        "Laboratory Trends": [
          {
            ...patientWorkspace.summary!.sections["Laboratory Trends"][0],
            citationIds: ["missing-citation"],
          },
        ],
      },
    },
  };

  render(<PatientWorkspace workspace={workspaceWithUnavailableCitation} onSave={async () => {}} onApprove={async () => {}} />);

  await user.click(screen.getByRole("button", { name: "missing-citation" }));

  expect(screen.getByRole("complementary", { name: "Source record" })).toHaveTextContent("Citation unavailable.");
});

it("saves an edited claim while retaining its citation token", async () => {
  const user = userEvent.setup();
  const onSave = vi.fn().mockResolvedValue(undefined);
  render(<PatientWorkspace workspace={patientWorkspace} onSave={onSave} onApprove={async () => {}} />);

  await user.clear(screen.getByLabelText("Edit claim-lab-1"));
  await user.type(screen.getByLabelText("Edit claim-lab-1"), "Creatinine trended down to 1.0 mg/dL.");
  await user.click(screen.getByRole("button", { name: "Revalidate and save draft" }));

  expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
    sections: expect.objectContaining({
      "Laboratory Trends": [expect.objectContaining({
        text: "Creatinine trended down to 1.0 mg/dL.",
        citationIds: ["labevent_id=9001"],
      })],
    }),
  }));
});
