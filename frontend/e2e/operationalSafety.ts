export const forbiddenClinicalFields = [
  "anchor_age",
  "gender",
  "source_row_key",
  "valuenum",
  "valueuom",
  "charttime",
  "raw_value",
] as const;

export function containsOnlyOperationalMetadata(serializedPayload: string): boolean {
  const normalizedPayload = serializedPayload.toLowerCase();
  return forbiddenClinicalFields.every((field) => !normalizedPayload.includes(field));
}
