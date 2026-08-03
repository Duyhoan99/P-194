import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AuditTable } from "@/components/AuditTable";

const events = [
  {
    actor: "admin-1",
    action: "REVOKE_CLINICAL_SUBJECT",
    subjectReference: "subject-101",
    timestamp: "2026-08-03T12:00:00Z",
    result: "SUCCESS",
    traceId: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  },
  {
    actor: "doctor-1",
    action: "VIEW_LABS",
    subjectReference: "subject-101",
    timestamp: "2026-08-03T11:00:00Z",
    result: "DENIED",
    traceId: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  },
];

it("filters append-only safe audit metadata by actor and result", async () => {
  const user = userEvent.setup();
  render(<AuditTable events={events} />);

  expect(screen.getAllByRole("row")).toHaveLength(3);

  await user.selectOptions(screen.getByLabelText("Actor"), "admin-1");
  await user.selectOptions(screen.getByLabelText("Result"), "SUCCESS");

  expect(screen.getAllByRole("row")).toHaveLength(2);
  expect(screen.getByRole("row", { name: /admin-1.*REVOKE_CLINICAL_SUBJECT.*SUCCESS/i })).toBeInTheDocument();
  expect(screen.queryByRole("row", { name: /doctor-1.*VIEW_LABS.*DENIED/i })).not.toBeInTheDocument();
  expect(screen.queryByText("raw value")).not.toBeInTheDocument();
});
