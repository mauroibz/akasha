/**
 * The hand-written API types, held to the generated contract (Sprint 088).
 *
 * `schema.d.ts` is generated from `openapi.json` by `npm run api:generate`, and
 * `npm run api:check` fails when it is stale. Each line below says a hand-written
 * type may only name fields the server's response model has, so a field renamed
 * or removed on the server fails `tsc` here instead of failing a page at runtime.
 * The hand types stay because several are deliberately narrower than the schema
 * (string unions the server types as `str`).
 */
import type { AuthSession, AuthUser, ManagedUser } from "./auth";
import type { ExportViewDefinition } from "./exports";
import type { ProviderHealth, ProviderStatus } from "./health";
import type {
  ImportBrowseListing,
  ImporterDefinition,
  ImportFileResult,
  ImportInputSpec,
  ImportPlanResult,
  ImportPreview,
  ImportRecord,
  ImportResult,
  JobProgress,
} from "./imports";
import type { CreateEntryResponse, SearchCandidate, SourceRef } from "./add";
import type { DuplicatePair } from "./duplicates";
import type { Loan, LoanWithEntry, Location } from "./loans";
import type {
  Attachment,
  BulkBody,
  ColumnSpec,
  CoverCandidate,
  CoverCandidates,
  FieldSpec,
  FormatSpec,
  Insight,
  InsightRow,
  InsightSuppressed,
  ItemType,
  LibraryEntry,
  LibraryItem,
  LibraryPage,
  ProgressSpec,
  ScoreDistribution,
  ScoreEvent,
  Shelf,
  StatusSpec,
} from "./library";
import type { components } from "./schema";

type Schemas = components["schemas"];

/** `true` when every field of `Hand` exists on the generated `Generated`. */
type NamesOnly<Hand, Generated> =
  Exclude<keyof Hand, keyof Generated> extends never
    ? true
    : { unknownFields: Exclude<keyof Hand, keyof Generated> };

type Holds<T extends true> = T;

export type Contract = [
  Holds<NamesOnly<AuthUser, Schemas["UserResponse"]>>,
  Holds<NamesOnly<ManagedUser, Schemas["UserSummary"]>>,
  Holds<NamesOnly<AuthSession, Schemas["SessionResponse"]>>,
  Holds<NamesOnly<ExportViewDefinition, Schemas["ExportViewResponse"]>>,
  Holds<NamesOnly<ProviderHealth, Schemas["ProviderHealth"]>>,
  Holds<NamesOnly<ProviderStatus, Schemas["ProviderStatus"]>>,
  Holds<NamesOnly<ImportBrowseListing, Schemas["ImportBrowseResponse"]>>,
  Holds<NamesOnly<ImporterDefinition, Schemas["ImporterResponse"]>>,
  Holds<NamesOnly<ImportFileResult, Schemas["ImportFileResponse"]>>,
  Holds<NamesOnly<ImportInputSpec, Schemas["ImportInputResponse"]>>,
  Holds<NamesOnly<ImportPlanResult, Schemas["ImportPlanResponse"]>>,
  Holds<NamesOnly<ImportPreview, Schemas["PreviewResponse"]>>,
  Holds<NamesOnly<ImportRecord, Schemas["ImportRecordResponse"]>>,
  Holds<NamesOnly<ImportResult, Schemas["CommitResponse"]>>,
  Holds<NamesOnly<JobProgress, Schemas["JobProgressResponse"]>>,
  Holds<NamesOnly<CreateEntryResponse, Schemas["EntryCreateResponse"]>>,
  Holds<NamesOnly<SearchCandidate, Schemas["SearchCandidateResponse"]>>,
  Holds<NamesOnly<SourceRef, Schemas["SourceRefResponse"]>>,
  Holds<NamesOnly<Attachment, Schemas["AttachmentResponse"]>>,
  Holds<NamesOnly<BulkBody, Schemas["BulkBody"]>>,
  Holds<NamesOnly<ColumnSpec, Schemas["ColumnSpecResponse"]>>,
  Holds<NamesOnly<CoverCandidate, Schemas["CoverCandidate"]>>,
  Holds<NamesOnly<CoverCandidates, Schemas["CoverCandidates"]>>,
  Holds<NamesOnly<FieldSpec, Schemas["FieldSpecResponse"]>>,
  Holds<NamesOnly<FormatSpec, Schemas["FormatSpecResponse"]>>,
  Holds<NamesOnly<Insight, Schemas["InsightResponse"]>>,
  Holds<NamesOnly<InsightRow, Schemas["InsightRowResponse"]>>,
  Holds<NamesOnly<InsightSuppressed, Schemas["InsightSuppressedResponse"]>>,
  Holds<NamesOnly<ItemType, Schemas["ItemTypeResponse"]>>,
  Holds<NamesOnly<LibraryEntry, Schemas["EntryResponse"]>>,
  Holds<NamesOnly<LibraryItem, Schemas["ItemResponse"]>>,
  Holds<NamesOnly<LibraryPage, Schemas["EntryListResponse"]>>,
  Holds<NamesOnly<ProgressSpec, Schemas["ProgressSpecResponse"]>>,
  Holds<NamesOnly<ScoreDistribution, Schemas["ScoreDistributionResponse"]>>,
  Holds<NamesOnly<Shelf, Schemas["ShelfResponse"]>>,
  Holds<NamesOnly<StatusSpec, Schemas["StatusSpecResponse"]>>,
  Holds<NamesOnly<Loan, Schemas["LoanResponse"]>>,
  Holds<NamesOnly<LoanWithEntry, Schemas["LoanWithEntryResponse"]>>,
  Holds<NamesOnly<Location, Schemas["LocationResponse"]>>,
  Holds<NamesOnly<DuplicatePair, Schemas["DuplicatePairResponse"]>>,
  Holds<NamesOnly<ScoreEvent, Schemas["ScoreEventResponse"]>>,
];
