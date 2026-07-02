// Reframe edit shape (mirror of reframe/schema.py Edit). The LLM proposer
// returns these; the client-side guard validates each against the source resume
// before anything is shown as an accepted change.
export type ChangeType = "relabel" | "reemphasis";
export type FieldName = "headline" | "summary" | "bullet" | "skills";

export interface Edit {
  field: FieldName;
  change_type: ChangeType;
  source_span: string;
  before: string;
  after: string;
  surfaced_keywords: string[];
  rationale: string;
}

export interface Lexicon {
  certs: string[];
  systems: string[];
  clearinghouses: string[];
  insurers: string[];
  codesets: string[];
  org_suffixes: string[];
  generic_acronyms: string[];
  acronym_map: Record<string, string>;
}
