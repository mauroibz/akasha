import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import type { SearchCandidate } from "@/api/add";
import type { FieldSpec } from "@/api/library";
import { CandidateFacts } from "./CandidateFacts";

const candidate: SearchCandidate = {
  source: "openlibrary",
  source_id: "OL1M",
  source_refs: [{ source: "openlibrary", source_id: "OL1M" }],
  title: "Rayuela",
  subtitle: null,
  creators: ["Julio Cortázar"],
  credit: "Julio Cortázar",
  year: 1963,
  cover_url: null,
  identifiers: {},
  language: "es",
  metadata: {
    publisher: "Sudamericana",
    description:
      "A paragraph long enough that a single grid column turns it into a ribbon.",
  },
};

const fields: FieldSpec[] = [
  { name: "publisher", label: "Publisher", type: "text", multiplicity: "one" },
  {
    name: "description",
    label: "Description",
    type: "long_text",
    multiplicity: "one",
  },
];

test("a long_text fact spans the grid and a short one does not", () => {
  render(<CandidateFacts candidate={candidate} fields={fields} />);

  const block = screen.getByText("Description").closest("[data-block-fact]");
  expect(block).not.toBeNull();
  expect(block).toHaveTextContent("turns it into a ribbon");

  // The rule is the declared type, not the field's name: a short fact keeps its
  // single column beside its neighbours.
  expect(screen.getByText("Publisher").closest("[data-block-fact]")).toBeNull();
});

test("the block fact comes after the facts it is long compared to", () => {
  const { container } = render(
    <CandidateFacts candidate={candidate} fields={fields} />,
  );

  const labels = Array.from(container.querySelectorAll("dt")).map(
    (node) => node.textContent,
  );
  expect(labels.indexOf("Description")).toBeGreaterThan(
    labels.indexOf("Publisher"),
  );
});
