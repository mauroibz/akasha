/**
 * The permanent credit line naming the sources of series data.
 *
 * TVmaze's licence is CC BY-SA and asks that TVmaze be "properly credited as
 * source"; the owner directed that the credit be given (DEC-105). This is one
 * line of copy and one of markup, mounted at the shell so it is findable from
 * every screen without hunting — the alternative to a visible line was chosen
 * against on purpose.
 */
export function DataCredit() {
  return (
    <p className="px-6 pb-4 text-center text-xs text-muted-foreground">
      Series data from{" "}
      <a
        href="https://www.wikidata.org"
        target="_blank"
        rel="noreferrer"
        className="underline underline-offset-2 hover:text-foreground"
      >
        Wikidata
      </a>{" "}
      and{" "}
      <a
        href="https://www.tvmaze.com"
        target="_blank"
        rel="noreferrer"
        className="underline underline-offset-2 hover:text-foreground"
      >
        TVmaze
      </a>
      .
    </p>
  );
}
