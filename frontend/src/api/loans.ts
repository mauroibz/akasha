import type { LibraryEntry } from "./library";
import { jsonOrApiError, readApiError, request } from "./request";

/** Who has it, since when, and when it came back (Sprint 110, DEC-176). */
export interface Loan {
  id: number;
  entry_id: number;
  person: string;
  /** `YYYY-MM-DD`, the owner's own day. */
  lent_on: string;
  returned_on: string | null;
  note: string | null;
}

export interface LoanWithEntry extends Loan {
  entry: LibraryEntry;
}

/** A place written on an entry, and how many entries carry it. */
export interface Location {
  location: string;
  count: number;
}

const json = { Accept: "application/json", "Content-Type": "application/json" };

export function getEntryLoans(entryId: number, signal?: AbortSignal) {
  return request(`/api/entries/${entryId}/loans`, { signal }).then((r) =>
    jsonOrApiError<Loan[]>(r, "Loans could not be loaded"),
  );
}

export function lendEntry(
  entryId: number,
  loan: { person: string; lent_on: string; note?: string | null },
) {
  return request(`/api/entries/${entryId}/loans`, {
    method: "POST",
    headers: json,
    body: JSON.stringify(loan),
  }).then((r) => jsonOrApiError<Loan>(r, "The loan could not be saved"));
}

export function updateLoan(
  loanId: number,
  changes: Partial<Pick<Loan, "person" | "lent_on" | "returned_on" | "note">>,
) {
  return request(`/api/loans/${loanId}`, {
    method: "PATCH",
    headers: json,
    body: JSON.stringify(changes),
  }).then((r) => jsonOrApiError<Loan>(r, "The loan could not be saved"));
}

export async function deleteLoan(loanId: number): Promise<void> {
  const response = await request(`/api/loans/${loanId}`, { method: "DELETE" });
  if (!response.ok)
    throw await readApiError(response, "The loan could not be removed");
}

/** What is out now, longest out first; every loan when `open` is false. */
export function getLoans(open = true, signal?: AbortSignal) {
  return request(`/api/loans${open ? "?open=true" : ""}`, { signal }).then(
    (r) => jsonOrApiError<LoanWithEntry[]>(r, "Loans could not be loaded"),
  );
}

export function getLocations(signal?: AbortSignal) {
  return request("/api/locations", { signal }).then((r) =>
    jsonOrApiError<Location[]>(r, "Places could not be loaded"),
  );
}
