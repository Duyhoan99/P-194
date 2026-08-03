import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ReviewModal } from "@/components/ReviewModal";
import { draftSummary } from "@/test/fixtures";

it("keeps approve disabled until the checklist is complete", async () => {
  const user = userEvent.setup();

  render(
    <ReviewModal
      summary={{ ...draftSummary, conflicts: [] }}
      reviewerId="doctor-1"
      onApprove={async () => {}}
      onClose={() => {}}
    />,
  );

  expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
  await user.click(screen.getByLabelText("I reviewed the summary"));
  await user.click(screen.getByLabelText("I checked critical evidence"));
  await user.click(screen.getByLabelText("I understand AI is decision support only"));
  await user.click(screen.getByLabelText("I confirm my edits"));

  expect(screen.getByRole("button", { name: "Approve" })).toBeEnabled();
});

it("keeps approval unavailable when a conflict remains unresolved", () => {
  render(<ReviewModal summary={draftSummary} reviewerId="doctor-1" onApprove={async () => {}} onClose={() => {}} />);

  expect(screen.getByText("Medication source status")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
});
