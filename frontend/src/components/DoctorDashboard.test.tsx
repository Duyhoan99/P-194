import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { DoctorDashboard } from "@/components/DoctorDashboard";

const assignedPatients = [
  { subjectId: 101, anchorAge: 63, gender: "F", admissionCount: 1, icuStayCount: 1, summaryStatus: "DRAFT" as const },
];

it("filters only server-returned assigned patients", async () => {
  const user = userEvent.setup();
  render(<DoctorDashboard patients={assignedPatients} onOpenPatient={() => {}} />);

  await user.type(screen.getByLabelText("Search assigned patients"), "102");

  expect(screen.getByText("No assigned patients match this search.")).toBeInTheDocument();
  expect(screen.queryByText("Subject 102")).not.toBeInTheDocument();
});

it("renders an explicit unavailable state without patient details", () => {
  render(<DoctorDashboard patients={[]} error="Clinical API is unavailable." onOpenPatient={() => {}} />);

  expect(screen.getByRole("alert")).toHaveTextContent("Clinical API is unavailable.");
  expect(screen.queryByText(/Subject/)).not.toBeInTheDocument();
});
