import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { DoctorApp } from "@/components/DoctorApp";
import { ApiError, apiClient } from "@/lib/api";
import { patientWorkspace } from "@/test/fixtures";

afterEach(() => vi.restoreAllMocks());

it.each([401, 503])("clears clinical state and requires re-login after session expiry status %s", async (status) => {
  const user = userEvent.setup();
  vi.spyOn(apiClient, "demoLogin").mockResolvedValue(undefined);
  vi.spyOn(apiClient, "listPatients").mockResolvedValue([patientWorkspace.patient]);
  vi.spyOn(apiClient, "getPatientWorkspace").mockResolvedValue(patientWorkspace);
  vi.spyOn(apiClient, "generateSummary").mockRejectedValue(
    new ApiError(status, status === 503 ? "Clinical authentication is not configured." : "Session expired."),
  );

  render(<DoctorApp />);
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  await user.click(await screen.findByRole("button", { name: "Open workspace" }));
  await user.click(await screen.findByRole("button", { name: "Request regeneration" }));

  expect(await screen.findByRole("heading", { name: "Doctor review interface" })).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("Your session has expired. Please sign in again.");
  expect(screen.queryByRole("heading", { name: "Patient workspace" })).not.toBeInTheDocument();
});
