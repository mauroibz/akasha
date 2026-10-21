export interface paths {
  "/api/auth/act-as": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    /** Stop Acting As */
    delete: operations["stop_acting_as_api_auth_act_as_delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/auth/act-as/{user_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Start Acting As */
    post: operations["start_acting_as_api_auth_act_as__user_id__post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/auth/login": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Login */
    post: operations["login_api_auth_login_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/auth/me": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Me */
    get: operations["me_api_auth_me_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/auth/password": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /** Change Password */
    patch: operations["change_password_api_auth_password_patch"];
    trace?: never;
  };
  "/api/auth/session": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    /** Logout */
    delete: operations["logout_api_auth_session_delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/auth/sessions": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Sessions */
    get: operations["list_sessions_api_auth_sessions_get"];
    put?: never;
    post?: never;
    /** Logout Everywhere */
    delete: operations["logout_everywhere_api_auth_sessions_delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/auth/sessions/{session_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    /** Revoke Session */
    delete: operations["revoke_session_api_auth_sessions__session_id__delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/auth/setup": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Setup */
    post: operations["setup_api_auth_setup_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/diary": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Diary
     * @description What was finished in a year, by month (Sprint 098); this year when not asked.
     *
     *     Resolved per request: a default in the signature is evaluated once, at import, and
     *     a server running across New Year would keep showing the old one.
     */
    get: operations["diary_api_diary_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/enrichment/backfill": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Backfill Enrichment
     * @description Queue enrichment for persisted items a provider lookup could still improve.
     *
     *     Explicit and operator-driven: it only queues work, and the handler it queues fills
     *     empty fields only, so it can never overwrite a hand edit. Each domain is asked on
     *     its own identifier and its own incompleteness rule (DEC-067 row 3).
     */
    post: operations["backfill_enrichment_api_enrichment_backfill_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/entries": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Entries */
    get: operations["list_entries_api_entries_get"];
    put?: never;
    /** Create Entry */
    post: operations["create_entry_api_entries_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/entries/accept-suggested": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Accept Suggested */
    post: operations["accept_suggested_api_entries_accept_suggested_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/entries/bulk": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    /**
     * Bulk Delete Entries
     * @description Remove the selection's entries in one transaction (triage's Discard).
     *
     *     Same selection shape as `PATCH /entries/bulk`: explicit `entry_ids` or a
     *     server-side `filter` plus `excluded_entry_ids`, never both. Deleting has no
     *     `set` to send, so the body is the selection half alone.
     */
    delete: operations["bulk_delete_entries_api_entries_bulk_delete"];
    options?: never;
    head?: never;
    /** Bulk Entries */
    patch: operations["bulk_entries_api_entries_bulk_patch"];
    trace?: never;
  };
  "/api/entries/{entry_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Entry */
    get: operations["get_entry_api_entries__entry_id__get"];
    put?: never;
    post?: never;
    /** Delete Entry */
    delete: operations["delete_entry_api_entries__entry_id__delete"];
    options?: never;
    head?: never;
    /** Update Entry */
    patch: operations["update_entry_api_entries__entry_id__patch"];
    trace?: never;
  };
  "/api/events": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Events */
    get: operations["events_api_events_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/export": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Export */
    get: operations["export_api_export_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/export/{view}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Export View Route */
    get: operations["export_view_route_api_export__view__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/exports": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Available Exports */
    get: operations["available_exports_api_exports_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/health/live": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Live */
    get: operations["live_api_health_live_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/health/providers": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Provider Health
     * @description Which metadata providers are configured, so the UI can say search is degraded.
     *
     *     Deliberately separate from readiness: a missing API key must never make the
     *     application look down (technical spec 8).
     */
    get: operations["provider_health_api_health_providers_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/health/ready": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Ready */
    get: operations["ready_api_health_ready_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/import/batches/{batch_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    /** Undo Batch */
    delete: operations["undo_batch_api_import_batches__batch_id__delete"];
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/import/detect": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Detect
     * @description Which importer each dropped file belongs to, most confident first (Sprint 095).
     *
     *     Reads only the first `SNIFF_BYTES` of each file; nothing is staged or kept. A file
     *     nobody claims answers an empty list, and the screen says it cannot use it.
     */
    post: operations["detect_api_import_detect_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/import/jobs/{job_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Job Progress */
    get: operations["get_job_progress_api_import_jobs__job_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/import/jobs/{job_id}/retry": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Retry Job
     * @description Queue a failed job again, from the shell's activity list (Sprint 089).
     */
    post: operations["retry_job_api_import_jobs__job_id__retry_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/import/{importer_name}/batches/{batch_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Read Preview
     * @description Re-read one previewed batch without re-sending its source.
     *
     *     The preview POST is idempotent by fingerprint and remains the way in; this
     *     read exists because a batch in its matching phase is polled for minutes
     *     (Sprint 083), and re-uploading a file the server already staged to learn
     *     its progress is exactly the cost an idempotent read should not have.
     */
    get: operations["read_preview_api_import__importer_name__batches__batch_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/import/{importer_name}/batches/{batch_id}/files": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Attach File
     * @description Take one file the import wants and attach it to the item it belongs to.
     *
     *     One file per request, and that is the design rather than an implementation
     *     detail (DEC-083). Folding these into the preview bundle would bound the feature
     *     by the size of the whole library instead of by the size of one file, so a shelf
     *     of any size would eventually stop importing; here a 600-book library behaves
     *     exactly like an 18-book one, a file that cannot be stored costs one book rather
     *     than the import, and the screen can count progress honestly.
     */
    post: operations["attach_file_api_import__importer_name__batches__batch_id__files_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/import/{importer_name}/batches/{batch_id}/records/{record_id}/exclude": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Exclude Row
     * @description Keep one row out of the commit entirely.
     *
     *     The owner's 2026-09-14 decision: 'none of these is the book' must not
     *     force a keep-as-typed row into the library. The row's planned action
     *     becomes `excluded` — commit's existing skip set — and the summary
     *     recounts so the commit gate tells the truth. Every connector's rows can
     *     be excluded; the route is shared surface, reached from the list
     *     connector's screen today.
     */
    post: operations["exclude_row_api_import__importer_name__batches__batch_id__records__record_id__exclude_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/import/{importer_name}/batches/{batch_id}/records/{record_id}/include": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Include Row
     * @description Undo a row's exclusion: it returns to what preview planned for it.
     */
    post: operations["include_row_api_import__importer_name__batches__batch_id__records__record_id__include_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/import/{importer_name}/batches/{batch_id}/records/{record_id}/proposal": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Answer Row Proposal
     * @description Confirm one proposal for one row, or discard the row's proposals.
     *
     *     Confirming re-stages the row's item half from the provider's payload and
     *     recomputes its planned action, so the commit that follows needs no new path
     *     (Sprint 083 D4). Discarding keeps the row exactly as the spreadsheet typed
     *     it. Both require the batch's searches to have drained.
     */
    post: operations["answer_row_proposal_api_import__importer_name__batches__batch_id__records__record_id__proposal_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/import/{importer_name}/batches/{batch_id}/records/{record_id}/search": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Research Row
     * @description Edit a row's title/author and search it again.
     *
     *     The owner's 2026-09-14 decision, available on any row (a bad query can
     *     also produce wrong proposals, not only an empty result): the typed row is
     *     re-staged with the edited text and its proposals are replaced. The spend
     *     is interactive-shaped (DEC-045): recorded, never blocked — a person is
     *     waiting on the answer.
     */
    post: operations["research_row_api_import__importer_name__batches__batch_id__records__record_id__search_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/import/{importer_name}/browse": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Browse
     * @description List what one folder under a browsable connector's source holds.
     *
     *     Read-only and confined by the connector itself, which resolves the request exactly
     *     as its reader would — the picker cannot walk anywhere a preview could not open.
     */
    get: operations["browse_api_import__importer_name__browse_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/import/{importer_name}/commit": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Commit */
    post: operations["commit_api_import__importer_name__commit_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/import/{importer_name}/plan": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Plan
     * @description Say which of the offered files are worth sending, before they are sent.
     *
     *     The client uploads the cheap half of the source — for Calibre, `metadata.db` — plus
     *     a manifest of what it is holding back. The connector answers from identities the
     *     library already has, because the client cannot hash: `crypto.subtle` is undefined on
     *     the plain-HTTP LAN origin this is served from (DEC-082).
     */
    post: operations["plan_api_import__importer_name__plan_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/import/{importer_name}/preview": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Preview */
    post: operations["preview_api_import__importer_name__preview_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/importers": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Available Importers */
    get: operations["available_importers_api_importers_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/insights": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Insights
     * @description Rank one domain's entries by a declared key (Sprint 065).
     */
    get: operations["get_insights_api_insights_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/insights/scores": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Get Score Distribution
     * @description Per-score counts for one domain (Sprint 073 deliverable 4).
     */
    get: operations["get_score_distribution_api_insights_scores_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/item-types": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Item Types
     * @description The domains this build knows, and the metadata fields each one declares.
     */
    get: operations["list_item_types_api_item_types_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/items/{item_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Item */
    get: operations["get_item_api_items__item_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    /** Update Item */
    patch: operations["update_item_api_items__item_id__patch"];
    trace?: never;
  };
  "/api/items/{item_id}/attachments": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Attachments */
    get: operations["list_attachments_api_items__item_id__attachments_get"];
    put?: never;
    /**
     * Add Attachment
     * @description Take an opaque file and store it by the digest of its contents.
     *
     *     The uploaded name is never trusted as a path. `os.path.basename` strips any
     *     directory a client put in front of it, and even that is belt-and-braces: the
     *     name is stored in the database and the blob is addressed by its own hash, so
     *     there is no code path where this string reaches the filesystem (DEC-048).
     */
    post: operations["add_attachment_api_items__item_id__attachments_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/items/{item_id}/attachments/{attachment_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Download Attachment
     * @description Serve an opaque blob in the only way that is safe from this origin.
     *
     *     Everything the application served before this endpoint had been re-encoded to
     *     a JPEG by the cover pipeline, so content type was never attacker-controlled.
     *     It is here, and the SPA shares this origin, so an uploaded HTML or SVG opened
     *     inline could script the application against its own API. The three headers
     *     below are what stop that, and none of them is optional (DEC-048).
     */
    get: operations["download_attachment_api_items__item_id__attachments__attachment_id__get"];
    put?: never;
    post?: never;
    /** Delete Attachment */
    delete: operations["delete_attachment_api_items__item_id__attachments__attachment_id__delete"];
    options?: never;
    head?: never;
    /**
     * Rename Attachment
     * @description Rename an attached file. One database write; the bytes are not involved.
     */
    patch: operations["rename_attachment_api_items__item_id__attachments__attachment_id__patch"];
    trace?: never;
  };
  "/api/items/{item_id}/cover": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Get Cover */
    get: operations["get_cover_api_items__item_id__cover_get"];
    put?: never;
    /**
     * Replace Cover
     * @description Replace a cover, either with an upload or with a candidate the owner picked.
     *
     *     One endpoint rather than two because the write is identical past the point the bytes
     *     are obtained: same validation, same atomic install, same recovery of the previous
     *     cover if anything fails.
     */
    post: operations["replace_cover_api_items__item_id__cover_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/items/{item_id}/cover-candidates": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * List Cover Candidates
     * @description Other editions of this work, offered as covers to choose from.
     *
     *     Only ever reached because a chooser was opened. Nothing here runs while a library
     *     page renders, which is the invariant that keeps cached pages provider-free.
     */
    get: operations["list_cover_candidates_api_items__item_id__cover_candidates_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/items/{item_id}/cover/fetch": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /**
     * Fetch Cover
     * @description Install a cover from the item's own primary provider, and nothing else.
     *
     *     `Refresh from provider` already does this as a side effect, but only after
     *     overwriting every other provider-managed field and behind a confirmation
     *     dialog — the wrong shape for the one case this exists for: a cover that
     *     never installed at add time (a transient fetch failure, a since-fixed
     *     provider outage) and nothing else about the record is wrong. Nothing here
     *     is destructive, so unlike refresh it needs no confirmation and no
     *     `overwrite` flag.
     */
    post: operations["fetch_cover_api_items__item_id__cover_fetch_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/items/{item_id}/refresh": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    /** Refresh Item */
    post: operations["refresh_item_api_items__item_id__refresh_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/now": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Now
     * @description Entries under way across every domain: the library's Now strip (Sprint 098).
     */
    get: operations["now_api_now_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/search": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Search */
    get: operations["search_api_search_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/search/library": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Search Library
     * @description Your entries for a query, best first: the command bar's library half (Sprint 094).
     */
    get: operations["search_library_api_search_library_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/search/preview": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /**
     * Preview
     * @description One candidate's full record, fetched without adding anything.
     *
     *     A search result carries an identity — title, creators, year, language, ISBNs —
     *     but not a description, a page count or a tracklist: those live in the per-item
     *     fetch that used to run only at add time, which is why the confirm screen had
     *     nothing to show. This is that fetch, on demand and writing nothing.
     *
     *     It follows `search`'s quota rule rather than enrichment's (DEC-045): the spend is
     *     recorded and never blocked, because somebody is waiting for this one. It is a
     *     request per press, so the screen asks rather than fetching on every click.
     */
    get: operations["preview_api_search_preview_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/search/resolve": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** Resolve */
    get: operations["resolve_api_search_resolve_get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/shelves": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Shelves */
    get: operations["list_shelves_api_shelves_get"];
    put?: never;
    /** Create Shelf */
    post: operations["create_shelf_api_shelves_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/shelves/{shelf_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    /** Delete Shelf */
    delete: operations["delete_shelf_api_shelves__shelf_id__delete"];
    options?: never;
    head?: never;
    /** Rename Shelf */
    patch: operations["rename_shelf_api_shelves__shelf_id__patch"];
    trace?: never;
  };
  "/api/users": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    /** List Users */
    get: operations["list_users_api_users_get"];
    put?: never;
    /** Create User */
    post: operations["create_user_api_users_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/users/{user_id}": {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    get?: never;
    put?: never;
    post?: never;
    /** Delete User */
    delete: operations["delete_user_api_users__user_id__delete"];
    options?: never;
    head?: never;
    /** Update User */
    patch: operations["update_user_api_users__user_id__patch"];
    trace?: never;
  };
}
export type webhooks = Record<string, never>;
export interface components {
  schemas: {
    /** AcceptSuggestedBody */
    AcceptSuggestedBody: {
      filter: components["schemas"]["EntryFilter"];
    };
    /** AffectedResponse */
    AffectedResponse: {
      /** Affected */
      affected: number;
    };
    /** AmbiguityChoice */
    AmbiguityChoice: {
      /** Item Id */
      item_id?: number | null;
      /** Record Id */
      record_id: number;
    };
    /** AttachmentList */
    AttachmentList: {
      /** Attachments */
      attachments: components["schemas"]["AttachmentResponse"][];
    };
    /** AttachmentRename */
    AttachmentRename: {
      /** Filename */
      filename: string;
    };
    /** AttachmentResponse */
    AttachmentResponse: {
      /** Byte Size */
      byte_size: number;
      /** Created At */
      created_at: string;
      /** Filename */
      filename: string;
      /** Id */
      id: number;
      /** Sha256 */
      sha256: string;
    };
    /** BackfillResponse */
    BackfillResponse: {
      /** Queued */
      queued: number;
    };
    /** Body_add_attachment_api_items__item_id__attachments_post */
    Body_add_attachment_api_items__item_id__attachments_post: {
      /**
       * File
       * Format: binary
       */
      file: string;
    };
    /** Body_detect_api_import_detect_post */
    Body_detect_api_import_detect_post: {
      /** Files */
      files: string[];
    };
    /** Body_replace_cover_api_items__item_id__cover_post */
    Body_replace_cover_api_items__item_id__cover_post: {
      /** Cover */
      cover?: string | null;
    };
    /** BulkBody */
    BulkBody: {
      /** Entry Ids */
      entry_ids?: number[] | null;
      /** Excluded Entry Ids */
      excluded_entry_ids?: number[];
      filter?: components["schemas"]["EntryFilter"] | null;
      set: components["schemas"]["BulkSet"];
    };
    /**
     * BulkSelection
     * @description The selection half of a bulk request — the one shape every bulk action
     *     resolves, so *Discard* understands the same `entry_ids`-or-`filter`
     *     selection the action bar already sends everywhere else.
     */
    BulkSelection: {
      /** Entry Ids */
      entry_ids?: number[] | null;
      /** Excluded Entry Ids */
      excluded_entry_ids?: number[];
      filter?: components["schemas"]["EntryFilter"] | null;
    };
    /** BulkSet */
    BulkSet: {
      /** Add Formats */
      add_formats?: string[];
      /** Add Shelves */
      add_shelves?: number[];
      /**
       * Clear Provisional
       * @default false
       */
      clear_provisional: boolean;
      /** Remove Formats */
      remove_formats?: string[];
      /** Remove Shelves */
      remove_shelves?: number[];
      /** Score */
      score?: number | null;
      status?: components["schemas"]["EntryStatus"] | null;
    };
    /** ChangePasswordBody */
    ChangePasswordBody: {
      /**
       * Current Password
       * Format: password
       */
      current_password: string;
      /**
       * New Password
       * Format: password
       */
      new_password: string;
    };
    /** ColumnSpecResponse */
    ColumnSpecResponse: {
      /** Label */
      label: string;
      /** Name */
      name: string;
      /** Type */
      type: string;
    };
    /** CommitBody */
    CommitBody: {
      /** Batch Id */
      batch_id: string;
      /** Choices */
      choices?: components["schemas"]["AmbiguityChoice"][];
    };
    /** CommitResponse */
    CommitResponse: {
      /** Batch Id */
      batch_id: string;
      /** Created Entries */
      created_entries: number;
      /** Created Items */
      created_items: number;
      /** State */
      state: string;
      /** Unchanged Entries */
      unchanged_entries: number;
      /** Unsorted Entries */
      unsorted_entries: number;
    };
    /** CoverCandidate */
    CoverCandidate: {
      /** Cover Url */
      cover_url: string;
      /** Source Id */
      source_id: string;
      /** Title */
      title: string;
      /** Year */
      year?: number | null;
    };
    /** CoverCandidates */
    CoverCandidates: {
      /** Candidates */
      candidates: components["schemas"]["CoverCandidate"][];
      /** Reason */
      reason?: string | null;
    };
    /** CreateUserBody */
    CreateUserBody: {
      /** Display Name */
      display_name?: string | null;
      /**
       * Is Admin
       * @default false
       */
      is_admin: boolean;
      /**
       * Password
       * Format: password
       */
      password: string;
      /** Username */
      username: string;
    };
    /** DeleteUserBody */
    DeleteUserBody: {
      /**
       * Action
       * @enum {string}
       */
      action: "transfer" | "delete";
      /** Transfer To User Id */
      transfer_to_user_id?: number | null;
    };
    /** DetectResponse */
    DetectResponse: {
      /** Files */
      files: components["schemas"]["DetectedFile"][];
    };
    /** DetectedFile */
    DetectedFile: {
      /** Matches */
      matches: components["schemas"]["DetectedMatch"][];
      /** Name */
      name: string;
    };
    /** DetectedMatch */
    DetectedMatch: {
      /** Confidence */
      confidence: number;
      /** Importer */
      importer: string;
    };
    /** DiaryMonth */
    DiaryMonth: {
      /** Counts */
      counts: {
        [key: string]: number;
      };
      /** Entries */
      entries: components["schemas"]["EntryResponse"][];
      /** Month */
      month: string;
    };
    /** DiaryResponse */
    DiaryResponse: {
      /** Months */
      months: components["schemas"]["DiaryMonth"][];
      /** Year */
      year: number;
      /** Years */
      years: number[];
    };
    /** EntryCreateBody */
    EntryCreateBody: {
      /**
       * Confirm Near Match
       * @default false
       */
      confirm_near_match: boolean;
      /** Date Finished */
      date_finished?: string | null;
      /** Date Started */
      date_started?: string | null;
      /** Formats */
      formats?: string[];
      /** Idempotency Key */
      idempotency_key?: string | null;
      manual?: components["schemas"]["ManualItemBody"] | null;
      /** Notes */
      notes?: string | null;
      /** Progress */
      progress?: number | null;
      /** Reread Count */
      reread_count?: number | null;
      /** Score */
      score?: number | null;
      /** Shelf Ids */
      shelf_ids?: number[];
      /** Source */
      source?: string | null;
      /** Source Id */
      source_id?: string | null;
      /** Source Refs */
      source_refs?: components["schemas"]["SourceRefBody"][];
      status?: components["schemas"]["EntryStatus"] | null;
    };
    /** EntryCreateResponse */
    EntryCreateResponse: {
      /** Already Exists */
      already_exists: boolean;
      entry: components["schemas"]["EntryResponse"];
      /** Near Matches */
      near_matches: number[];
    };
    /** EntryFilter */
    EntryFilter: {
      /** Format */
      format?: components["schemas"]["EntryFormat"][];
      /** Q */
      q?: string | null;
      /** Shelf */
      shelf?: string[];
      /** Status */
      status?: components["schemas"]["EntryStatus"][] | null;
    };
    /**
     * EntryFormat
     * @description The published union of every domain's formats, for filters and facets.
     * @enum {string}
     */
    EntryFormat:
      | "physical"
      | "borrowed"
      | "digital"
      | "vinyl"
      | "cd"
      | "streaming"
      | "bluray"
      | "dvd";
    /** EntryListResponse */
    EntryListResponse: {
      facets: components["schemas"]["FacetsResponse"];
      /** Items */
      items: components["schemas"]["EntryResponse"][];
      /** Next Cursor */
      next_cursor: string | null;
      /** Total */
      total: number;
    };
    /** EntryPatch */
    EntryPatch: {
      /** Date Finished */
      date_finished?: string | null;
      /** Date Started */
      date_started?: string | null;
      /** Formats */
      formats?: string[] | null;
      /** Notes */
      notes?: string | null;
      /** Progress */
      progress?: number | null;
      /** Reread Count */
      reread_count?: number | null;
      /** Score */
      score?: number | null;
      /** Shelf Ids */
      shelf_ids?: number[] | null;
      status?: components["schemas"]["EntryStatus"] | null;
    };
    /** EntryResponse */
    EntryResponse: {
      /** Date Added */
      date_added: string;
      /** Date Finished */
      date_finished: string | null;
      /** Date Started */
      date_started: string | null;
      /** Formats */
      formats: string[];
      /** Id */
      id: number;
      item: components["schemas"]["ItemResponse"];
      /** Item Id */
      item_id: number;
      /** Notes */
      notes: string | null;
      /** Progress */
      progress: number | null;
      /** Reread Count */
      reread_count: number;
      /** Score */
      score: number | null;
      /** Score Provisional */
      score_provisional: boolean;
      /** Shelves */
      shelves: components["schemas"]["ShelfResponse"][];
      status: components["schemas"]["EntryStatus"];
      suggested_status: components["schemas"]["EntryStatus"] | null;
    };
    /**
     * EntryStatus
     * @description The published union, so OpenAPI enumerates what a client may send.
     *
     *     Spelled out rather than built from `ALL_STATUSES`, because a dynamic enum is
     *     opaque to the type checker and this is a public surface. `test_domain.py` asserts
     *     the two agree, so adding a domain status and forgetting this fails a test instead
     *     of quietly dropping the value from the API contract.
     *
     *     It is not the authority on what is legal for a given item: that is
     *     `validate_status`, keyed on the item's own type (seam 5b).
     * @enum {string}
     */
    EntryStatus:
      | "unsorted"
      | "read"
      | "reading"
      | "to_read"
      | "wishlist"
      | "dropped"
      | "pending"
      | "owned"
      | "watching"
      | "completed"
      | "on_hold"
      | "plan_to_watch"
      | "watchlist"
      | "watched";
    /** ErrorDetail */
    ErrorDetail: {
      /** Code */
      code: string;
      /** Details */
      details: {
        [key: string]: unknown;
      };
      /** Message */
      message: string;
    };
    /** ErrorResponse */
    ErrorResponse: {
      error: components["schemas"]["ErrorDetail"];
    };
    /**
     * ExportViewResponse
     * @description One declared view, shaped like `ImporterResponse` (DEC-080's pattern, pointed
     *     the other way): a screen renders this without knowing which view it is holding.
     */
    ExportViewResponse: {
      /** Carries */
      carries: string[];
      /** Count */
      count: number;
      /** Guide */
      guide: string[];
      /** Help Url */
      help_url?: string | null;
      /** Id */
      id: string;
      /** Item Types */
      item_types: string[];
      /** Label */
      label: string;
      /** Lossless */
      lossless: boolean;
      /** Media Type */
      media_type: string;
    };
    /** FacetsResponse */
    FacetsResponse: {
      /** Format Counts */
      format_counts: {
        [key: string]: number;
      };
      /** Status Counts */
      status_counts: {
        [key: string]: number;
      };
      /** Status Counts By Type */
      status_counts_by_type: {
        [key: string]: {
          [key: string]: number;
        };
      };
    };
    /** FieldSpecResponse */
    FieldSpecResponse: {
      /** Columns */
      columns?: components["schemas"]["ColumnSpecResponse"][] | null;
      /**
       * Groupable
       * @default false
       */
      groupable: boolean;
      /** Label */
      label: string;
      /** Maximum */
      maximum?: number | null;
      /** Minimum */
      minimum?: number | null;
      /** Multiplicity */
      multiplicity: string;
      /** Name */
      name: string;
      /** Type */
      type: string;
    };
    /** FormatSpecResponse */
    FormatSpecResponse: {
      /** Label */
      label: string;
      /** Value */
      value: string;
    };
    /**
     * ImportBrowseResponse
     * @description One level of a browsable connector's source. Relative names only.
     */
    ImportBrowseResponse: {
      /** Directories */
      directories?: string[];
      /**
       * Importable
       * @default false
       */
      importable: boolean;
      /** Parent */
      parent?: string | null;
      /** Path */
      path: string;
    };
    /** ImportFileResponse */
    ImportFileResponse: {
      /** Byte Size */
      byte_size: number;
      /** Filename */
      filename: string;
      /** Id */
      id: number;
      /** Item Id */
      item_id: number;
      /** Sha256 */
      sha256: string;
    };
    /** ImportInputResponse */
    ImportInputResponse: {
      /** Accept */
      accept?: string | null;
      /**
       * Accepts Files
       * @default false
       */
      accepts_files: boolean;
      /** Alternates */
      alternates?: components["schemas"]["ImportInputResponse"][];
      /**
       * Browsable
       * @default false
       */
      browsable: boolean;
      /** Empty State */
      empty_state?: string | null;
      /** Field */
      field: string;
      /** Fields */
      fields?: string[];
      /** Flags */
      flags?: string[];
      /** Guide */
      guide?: string[];
      /** Help */
      help?: string | null;
      /** Help Url */
      help_url?: string | null;
      /**
       * Incremental
       * @default false
       */
      incremental: boolean;
      /** Kind */
      kind: string;
      /** Label */
      label: string;
      /** Max Bytes */
      max_bytes?: number | null;
      /** Max Files */
      max_files?: number | null;
      /** Placeholder */
      placeholder?: string | null;
      /**
       * Quick Add
       * @default false
       */
      quick_add: boolean;
      /**
       * Single Domain Pick
       * @default false
       */
      single_domain_pick: boolean;
    };
    /**
     * ImportPlanResponse
     * @description Which offered members are worth uploading, and how many were skipped.
     */
    ImportPlanResponse: {
      /**
       * Holding
       * @default 0
       */
      holding: number;
      /** Reason */
      reason?: string | null;
      /** Wanted */
      wanted?: string[];
    };
    /** ImportRecordResponse */
    ImportRecordResponse: {
      /**
       * Attachment Staged
       * @default false
       */
      attachment_staged: boolean;
      /** Candidates */
      candidates: number[];
      /**
       * Cover Staged
       * @default false
       */
      cover_staged: boolean;
      /** Creators */
      creators: string[];
      /** Entry */
      entry: {
        [key: string]: unknown;
      };
      /** Errors */
      errors?: {
        [key: string]: unknown;
      }[];
      /** Item */
      item: {
        [key: string]: unknown;
      };
      /** Match Kind */
      match_kind: string;
      /** Planned Action */
      planned_action: string;
      /** Record Id */
      record_id: number;
      /** Row Number */
      row_number: number;
      /** Score */
      score?: number | null;
      /**
       * Score Provisional
       * @default false
       */
      score_provisional: boolean;
      /** Shelves */
      shelves?: string[];
      /** Source Fields */
      source_fields: {
        [key: string]: unknown;
      };
      /** Suggested Status */
      suggested_status?: string | null;
      /** Title */
      title: string;
    } & {
      [key: string]: unknown;
    };
    /** ImporterResponse */
    ImporterResponse: {
      /** Attachment Max Bytes */
      attachment_max_bytes: number;
      /** Id */
      id: string;
      input: components["schemas"]["ImportInputResponse"];
      /** Item Types */
      item_types: string[];
      /** Label */
      label: string;
    };
    /** InsightResponse */
    InsightResponse: {
      /** Key */
      key: string;
      /**
       * Metric
       * @enum {string}
       */
      metric: "count" | "score";
      /** Min Rated */
      min_rated: number;
      /** Next Cursor */
      next_cursor: string | null;
      /** No Rated Groups */
      no_rated_groups: boolean;
      /** Null Count */
      null_count: number;
      /** Rated Entries */
      rated_entries: number;
      /** Rows */
      rows: components["schemas"]["InsightRowResponse"][];
      /** Suppressed */
      suppressed: components["schemas"]["InsightSuppressedResponse"][];
      /** Total Entries */
      total_entries: number;
      /** Type */
      type: string;
    };
    /** InsightRowResponse */
    InsightRowResponse: {
      /** Count */
      count: number;
      /** Covers */
      covers: string[];
      /** Key */
      key: string;
      /** Label */
      label: string;
      /** Mean Score */
      mean_score: number | null;
      /** Rated Count */
      rated_count: number;
      /** Score Spread */
      score_spread: number | null;
    };
    /** InsightSuppressedResponse */
    InsightSuppressedResponse: {
      /** Count */
      count: number;
      /** Key */
      key: string;
      /** Label */
      label: string;
    };
    /** ItemPatch */
    ItemPatch: {
      /** Creator Sort Override */
      creator_sort_override?: string | null;
      /** Metadata */
      metadata?: {
        [key: string]: unknown;
      } | null;
      /** Subtitle */
      subtitle?: string | null;
      /** Title */
      title?: string | null;
      /** Year */
      year?: number | null;
    };
    /** ItemResponse */
    ItemResponse: {
      /** Cover Url */
      cover_url: string | null;
      /** Creator */
      creator: string | null;
      /** Creator Sort */
      creator_sort: string | null;
      /** Creator Sort Override */
      creator_sort_override: string | null;
      /** Id */
      id: number;
      /** Identifiers */
      identifiers: {
        [key: string]: string;
      };
      /** Metadata */
      metadata: {
        [key: string]: unknown;
      };
      /** Sources */
      sources: components["schemas"]["SourceResponse"][];
      /** Subtitle */
      subtitle: string | null;
      /** Title */
      title: string;
      /** Type */
      type: string;
      /** Year */
      year: number | null;
    };
    /**
     * ItemTypeName
     * @description The published union of domain names, so `?type=` enumerates in OpenAPI.
     *
     *     Spelled out for the same reason `EntryStatus` is, and pinned to `DOMAINS` by the
     *     same test. Unlike a status, a type is never validated against an item's own domain
     *     — it *is* the domain — so this enum is the whole check the filter needs.
     * @enum {string}
     */
    ItemTypeName: "book" | "album" | "anime" | "movie" | "series";
    /**
     * ItemTypeResponse
     * @description What a domain says about itself, so a screen can render it without branching.
     */
    ItemTypeResponse: {
      /** Chooses Covers */
      chooses_covers: boolean;
      /** Default Status */
      default_status: string;
      /** Entry Field Labels */
      entry_field_labels: {
        [key: string]: string;
      };
      /** Entry Fields */
      entry_fields: string[];
      /** Entry Panel Label */
      entry_panel_label: string;
      /** Fields */
      fields: components["schemas"]["FieldSpecResponse"][];
      /** Formats */
      formats: components["schemas"]["FormatSpecResponse"][];
      /** Id */
      id: string;
      /** Label */
      label: string;
      progress: components["schemas"]["ProgressSpecResponse"] | null;
      /** Statuses */
      statuses: components["schemas"]["StatusSpecResponse"][];
    };
    /** JobProgressResponse */
    JobProgressResponse: {
      /**
       * Attempts
       * @default 0
       */
      attempts: number;
      /** Batch Id */
      batch_id?: string | null;
      /** Created At */
      created_at: string;
      /** Error */
      error?: string | null;
      /** Error Code */
      error_code?: string | null;
      /** Finished At */
      finished_at?: string | null;
      /** Id */
      id: string;
      /** Kind */
      kind: string;
      /** Progress */
      progress?: {
        [key: string]: unknown;
      };
      /** State */
      state: string;
    };
    /** LoginBody */
    LoginBody: {
      /**
       * Password
       * Format: password
       */
      password: string;
      /** Username */
      username: string;
    };
    /** ManualItemBody */
    ManualItemBody: {
      /** Identifiers */
      identifiers?: {
        [key: string]: string;
      };
      item_type: components["schemas"]["ItemTypeName"];
      /** Metadata */
      metadata?: {
        [key: string]: unknown;
      };
      /** Subtitle */
      subtitle?: string | null;
      /** Title */
      title: string;
      /** Year */
      year?: number | null;
    };
    /** MeResponse */
    MeResponse: {
      acting_as: components["schemas"]["UserResponse"] | null;
      /** Auth */
      auth: string;
      /** Authenticated */
      authenticated: boolean;
      /** Setup Required */
      setup_required: boolean;
      user: components["schemas"]["UserResponse"] | null;
    };
    /** PreviewResponse */
    PreviewResponse: {
      /** Batch Id */
      batch_id: string;
      /** Fingerprint */
      fingerprint: string;
      /** Records */
      records: components["schemas"]["ImportRecordResponse"][];
      search_progress?: components["schemas"]["SearchProgress"] | null;
      /** State */
      state: string;
      summary: components["schemas"]["PreviewSummary"];
    };
    /** PreviewSummary */
    PreviewSummary: {
      /** Ambiguous */
      ambiguous: number;
      /** Errors */
      errors: number;
      /** Ready */
      ready: number;
      /**
       * Skipped Not Requested
       * @default 0
       */
      skipped_not_requested: number;
      /** Skipped Reasons */
      skipped_reasons?: components["schemas"]["SkippedReason"][];
      /**
       * Skipped Unsupported
       * @default 0
       */
      skipped_unsupported: number;
      /** Total */
      total: number;
    };
    /**
     * ProgressSpecResponse
     * @description How this domain counts progress, so a screen renders a declaration.
     *
     *     `total_field` names a metadata field on the *item*; it is for reading "20 / 170"
     *     and is never a bound (DEC-077, Sprint 040).
     */
    ProgressSpecResponse: {
      /** Label */
      label: string;
      /** Total Field */
      total_field: string | null;
      /** Unit Label */
      unit_label: string;
    };
    /**
     * ProposalAnswerBody
     * @description Which proposal the owner confirmed, or the explicit discard.
     *
     *     A connector without a search phase never sees this body: the route exists on
     *     the shared router, but `answer_proposal` refuses any batch that is not
     *     `previewed` with proposals — for every other connector the preview GET a
     *     confirm would need is already the answer.
     */
    ProposalAnswerBody: {
      /**
       * Discard
       * @default false
       */
      discard: boolean;
      /** Source */
      source?: string | null;
      /** Source Id */
      source_id?: string | null;
    };
    /** ProviderHealth */
    ProviderHealth: {
      /** Degraded */
      degraded: boolean;
      /** Providers */
      providers: components["schemas"]["ProviderStatus"][];
    };
    /** ProviderStatus */
    ProviderStatus: {
      /** Available */
      available: boolean;
      /** Name */
      name: string;
      /** Reason */
      reason?: string | null;
    };
    /** RefreshBody */
    RefreshBody: {
      /** Overwrite */
      overwrite: boolean;
    };
    /**
     * RowSearchBody
     * @description The edited text a re-search should query, either half optional.
     *
     *     An omitted half keeps the row's current value — the owner edits what is
     *     wrong and leaves the rest alone.
     */
    RowSearchBody: {
      /** Author */
      author?: string | null;
      /** Title */
      title?: string | null;
    };
    /** ScoreDistributionResponse */
    ScoreDistributionResponse: {
      /** Counts */
      counts: number[];
      /** Rated Count */
      rated_count: number;
      /** Type */
      type: string;
      /** Unrated Count */
      unrated_count: number;
    };
    /** SearchCandidateResponse */
    SearchCandidateResponse: {
      /** Cover Url */
      cover_url: string | null;
      /** Creators */
      creators: string[];
      /** Credit */
      credit: string | null;
      /** Identifiers */
      identifiers: {
        [key: string]: string;
      };
      /** Language */
      language: string | null;
      /** Metadata */
      metadata: {
        [key: string]: unknown;
      };
      /** Original Year */
      original_year: number | null;
      /** Source */
      source: string;
      /** Source Id */
      source_id: string;
      /** Source Refs */
      source_refs: components["schemas"]["SourceRefResponse"][];
      /** Subtitle */
      subtitle: string | null;
      /** Title */
      title: string;
      /** Year */
      year: number | null;
    };
    /**
     * SearchProgress
     * @description A matching batch's search job, so far (Sprint 083 D3.2).
     */
    SearchProgress: {
      /** Job State */
      job_state: string;
      /** Searched */
      searched: number;
      /** Total */
      total: number;
      /** Wait Reason */
      wait_reason?: string | null;
    };
    /** SessionResponse */
    SessionResponse: {
      /**
       * Created At
       * Format: date-time
       */
      created_at: string;
      /** Current */
      current: boolean;
      /** Id */
      id: string;
      /**
       * Last Seen At
       * Format: date-time
       */
      last_seen_at: string;
      /** User Agent */
      user_agent: string | null;
    };
    /** SetupBody */
    SetupBody: {
      /** Display Name */
      display_name?: string | null;
      /**
       * Password
       * Format: password
       */
      password: string;
      /** Username */
      username: string;
    };
    /** ShelfBody */
    ShelfBody: {
      /** Name */
      name: string;
    };
    /** ShelfResponse */
    ShelfResponse: {
      /** Covers */
      covers?: string[];
      /**
       * Entry Count
       * @default 0
       */
      entry_count: number;
      /** Id */
      id: number;
      /** Members By Type */
      members_by_type?: {
        [key: string]: number;
      };
      /** Name */
      name: string;
      /** Slug */
      slug: string;
      /** Updated At */
      updated_at: string;
    };
    /** SkippedReason */
    SkippedReason: {
      /** Count */
      count: number;
      /** Reason */
      reason: string;
    };
    /** SourceRefBody */
    SourceRefBody: {
      /** Source */
      source: string;
      /** Source Id */
      source_id: string;
    };
    /** SourceRefResponse */
    SourceRefResponse: {
      /** Source */
      source: string;
      /** Source Id */
      source_id: string;
    };
    /** SourceResponse */
    SourceResponse: {
      /** Is Primary */
      is_primary: boolean;
      /** Source */
      source: string;
      /** Source Id */
      source_id: string;
    };
    /** StatusSpecResponse */
    StatusSpecResponse: {
      /** Choosable */
      choosable: boolean;
      /** Hotkey */
      hotkey?: string | null;
      /**
       * In Progress
       * @default false
       */
      in_progress: boolean;
      /** Label */
      label: string;
      /** Value */
      value: string;
    };
    /** UndoEffectSummary */
    UndoEffectSummary: {
      /** Batch Id */
      batch_id: string;
      /** Retained */
      retained: number;
      /**
       * Retained Items
       * @default 0
       */
      retained_items: number;
      /** Reverted */
      reverted: number;
      /**
       * Reverted Entries
       * @default 0
       */
      reverted_entries: number;
      /**
       * Reverted Items
       * @default 0
       */
      reverted_items: number;
      /** Skipped */
      skipped: number;
      /** State */
      state: string;
    };
    /** UpdateUserBody */
    UpdateUserBody: {
      /** Display Name */
      display_name?: string | null;
      /** Is Admin */
      is_admin?: boolean | null;
      /** Password */
      password?: string | null;
    };
    /** UserResponse */
    UserResponse: {
      /** Display Name */
      display_name: string | null;
      /** Id */
      id: number;
      /** Is Admin */
      is_admin: boolean;
      /** Username */
      username: string;
    };
    /** UserSummary */
    UserSummary: {
      /** Display Name */
      display_name: string | null;
      /** Entry Count */
      entry_count: number;
      /** Id */
      id: number;
      /** Is Admin */
      is_admin: boolean;
      /** Shelf Count */
      shelf_count: number;
      /** Username */
      username: string;
    };
  };
  responses: never;
  parameters: never;
  requestBodies: never;
  headers: never;
  pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
  stop_acting_as_api_auth_act_as_delete: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  start_acting_as_api_auth_act_as__user_id__post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        user_id: number;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  login_api_auth_login_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["LoginBody"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["UserResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Too Many Requests */
      429: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  me_api_auth_me_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["MeResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  change_password_api_auth_password_patch: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ChangePasswordBody"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  logout_api_auth_session_delete: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  list_sessions_api_auth_sessions_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SessionResponse"][];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  logout_everywhere_api_auth_sessions_delete: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  revoke_session_api_auth_sessions__session_id__delete: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        session_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  setup_api_auth_setup_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["SetupBody"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["UserResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  diary_api_diary_get: {
    parameters: {
      query?: {
        year?: number | null;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["DiaryResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  backfill_enrichment_api_enrichment_backfill_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      202: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["BackfillResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  list_entries_api_entries_get: {
    parameters: {
      query?: {
        status?: components["schemas"]["EntryStatus"][] | null;
        shelf?: string[] | null;
        format?: components["schemas"]["EntryFormat"][] | null;
        type?: components["schemas"]["ItemTypeName"][] | null;
        q?: string | null;
        key?: string | null;
        value?: string | null;
        sort?:
          | "date_added"
          | "score"
          | "title"
          | "creator"
          | "year"
          | "date_finished";
        order?: "asc" | "desc";
        after?: string | null;
        limit?: number;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EntryListResponse"];
        };
      };
      /** @description Bad Request */
      400: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  create_entry_api_entries_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["EntryCreateBody"];
      };
    };
    responses: {
      /** @description OK */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EntryCreateResponse"];
        };
      };
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EntryCreateResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  accept_suggested_api_entries_accept_suggested_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["AcceptSuggestedBody"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AffectedResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  bulk_delete_entries_api_entries_bulk_delete: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["BulkSelection"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AffectedResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  bulk_entries_api_entries_bulk_patch: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["BulkBody"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AffectedResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_entry_api_entries__entry_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        entry_id: number;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EntryResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  delete_entry_api_entries__entry_id__delete: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        entry_id: number;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  update_entry_api_entries__entry_id__patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        entry_id: number;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["EntryPatch"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EntryResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  events_api_events_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  export_api_export_get: {
    parameters: {
      query?: {
        format?: "json" | "csv";
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  export_view_route_api_export__view__get: {
    parameters: {
      query: {
        type: components["schemas"]["ItemTypeName"];
      };
      header?: never;
      path: {
        view: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  available_exports_api_exports_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ExportViewResponse"][];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  live_api_health_live_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": {
            [key: string]: string;
          };
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  provider_health_api_health_providers_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ProviderHealth"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  ready_api_health_ready_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  undo_batch_api_import_batches__batch_id__delete: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        batch_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["UndoEffectSummary"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  detect_api_import_detect_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "multipart/form-data": components["schemas"]["Body_detect_api_import_detect_post"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["DetectResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_job_progress_api_import_jobs__job_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        job_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["JobProgressResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  retry_job_api_import_jobs__job_id__retry_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        job_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["JobProgressResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  read_preview_api_import__importer_name__batches__batch_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        importer_name: string;
        batch_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PreviewResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  attach_file_api_import__importer_name__batches__batch_id__files_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        importer_name: string;
        batch_id: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ImportFileResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  exclude_row_api_import__importer_name__batches__batch_id__records__record_id__exclude_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        importer_name: string;
        batch_id: string;
        record_id: number;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PreviewResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  include_row_api_import__importer_name__batches__batch_id__records__record_id__include_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        importer_name: string;
        batch_id: string;
        record_id: number;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PreviewResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  answer_row_proposal_api_import__importer_name__batches__batch_id__records__record_id__proposal_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        importer_name: string;
        batch_id: string;
        record_id: number;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ProposalAnswerBody"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PreviewResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  research_row_api_import__importer_name__batches__batch_id__records__record_id__search_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        importer_name: string;
        batch_id: string;
        record_id: number;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RowSearchBody"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PreviewResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  browse_api_import__importer_name__browse_get: {
    parameters: {
      query?: {
        path?: string;
      };
      header?: never;
      path: {
        importer_name: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ImportBrowseResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  commit_api_import__importer_name__commit_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        importer_name: string;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CommitBody"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CommitResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  plan_api_import__importer_name__plan_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        importer_name: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ImportPlanResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  preview_api_import__importer_name__preview_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        importer_name: string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["PreviewResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  available_importers_api_importers_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ImporterResponse"][];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_insights_api_insights_get: {
    parameters: {
      query: {
        type: components["schemas"]["ItemTypeName"];
        key: string;
        metric?: "count" | "score";
        min_rated?: number;
        include_suppressed?: boolean;
        status?: components["schemas"]["EntryStatus"][] | null;
        shelf?: string[] | null;
        format?: components["schemas"]["EntryFormat"][] | null;
        q?: string | null;
        limit?: number;
        after?: string | null;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["InsightResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_score_distribution_api_insights_scores_get: {
    parameters: {
      query: {
        type: components["schemas"]["ItemTypeName"];
        status?: components["schemas"]["EntryStatus"][] | null;
        shelf?: string[] | null;
        format?: components["schemas"]["EntryFormat"][] | null;
        q?: string | null;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ScoreDistributionResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  list_item_types_api_item_types_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ItemTypeResponse"][];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_item_api_items__item_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        item_id: number;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ItemResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  update_item_api_items__item_id__patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        item_id: number;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ItemPatch"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ItemResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  list_attachments_api_items__item_id__attachments_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        item_id: number;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AttachmentList"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  add_attachment_api_items__item_id__attachments_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        item_id: number;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "multipart/form-data": components["schemas"]["Body_add_attachment_api_items__item_id__attachments_post"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AttachmentResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  download_attachment_api_items__item_id__attachments__attachment_id__get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        item_id: number;
        attachment_id: number;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  delete_attachment_api_items__item_id__attachments__attachment_id__delete: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        item_id: number;
        attachment_id: number;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  rename_attachment_api_items__item_id__attachments__attachment_id__patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        item_id: number;
        attachment_id: number;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["AttachmentRename"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["AttachmentResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  get_cover_api_items__item_id__cover_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        item_id: number;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": unknown;
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  replace_cover_api_items__item_id__cover_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        item_id: number;
      };
      cookie?: never;
    };
    requestBody?: {
      content: {
        "multipart/form-data": components["schemas"]["Body_replace_cover_api_items__item_id__cover_post"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ItemResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  list_cover_candidates_api_items__item_id__cover_candidates_get: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        item_id: number;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["CoverCandidates"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  fetch_cover_api_items__item_id__cover_fetch_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        item_id: number;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ItemResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  refresh_item_api_items__item_id__refresh_post: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        item_id: number;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RefreshBody"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ItemResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  now_api_now_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EntryResponse"][];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  search_api_search_get: {
    parameters: {
      query: {
        q: string;
        type?: string;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SearchCandidateResponse"][];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  search_library_api_search_library_get: {
    parameters: {
      query: {
        q: string;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["EntryResponse"][];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  preview_api_search_preview_get: {
    parameters: {
      query: {
        source: string;
        source_id: string;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SearchCandidateResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  resolve_api_search_resolve_get: {
    parameters: {
      query: {
        url: string;
      };
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["SearchCandidateResponse"][];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  list_shelves_api_shelves_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ShelfResponse"][];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  create_shelf_api_shelves_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ShelfBody"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ShelfResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  delete_shelf_api_shelves__shelf_id__delete: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        shelf_id: number;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  rename_shelf_api_shelves__shelf_id__patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        shelf_id: number;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["ShelfBody"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ShelfResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Requested resource was not found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Domain conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  list_users_api_users_get: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["UserSummary"][];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  create_user_api_users_post: {
    parameters: {
      query?: never;
      header?: never;
      path?: never;
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["CreateUserBody"];
      };
    };
    responses: {
      /** @description Successful Response */
      201: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["UserResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  delete_user_api_users__user_id__delete: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        user_id: number;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["DeleteUserBody"];
      };
    };
    responses: {
      /** @description Successful Response */
      204: {
        headers: {
          [name: string]: unknown;
        };
        content?: never;
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
  update_user_api_users__user_id__patch: {
    parameters: {
      query?: never;
      header?: never;
      path: {
        user_id: number;
      };
      cookie?: never;
    };
    requestBody: {
      content: {
        "application/json": components["schemas"]["UpdateUserBody"];
      };
    };
    responses: {
      /** @description Successful Response */
      200: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["UserResponse"];
        };
      };
      /** @description Unauthorized */
      401: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Forbidden */
      403: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Not Found */
      404: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Conflict */
      409: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
      /** @description Unprocessable Entity */
      422: {
        headers: {
          [name: string]: unknown;
        };
        content: {
          "application/json": components["schemas"]["ErrorResponse"];
        };
      };
    };
  };
}
