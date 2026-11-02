export type Status = "answered" | "not_found" | "blocked";

export interface Citation {
  label: string;
  source_id: string;
  section: string;
  heading: string;
  page: number | null;
  excerpt: string;
  url: string;
}

export interface Answer {
  status: Status;
  text: string;
  citations: Citation[];
}
