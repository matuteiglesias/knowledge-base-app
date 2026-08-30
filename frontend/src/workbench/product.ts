export const WORKBENCH_TAB_IDS = ["corpus", "authors", "abstracts", "search", "paper"] as const;

export type WorkbenchTabId = (typeof WORKBENCH_TAB_IDS)[number];

export type WorkbenchTabDefinition = {
  id: WorkbenchTabId;
  label: string;
  description: string;
};

export type WorkbenchProduct = {
  id: string;
  label: string;
  description: string;
  tabs: WorkbenchTabId[];
  defaultTab: WorkbenchTabId;
};

export const TAB_CATALOG: Record<WorkbenchTabId, WorkbenchTabDefinition> = {
  corpus: {
    id: "corpus",
    label: "Corpus",
    description: "Browse the governed paper set and inspect metadata coverage.",
  },
  authors: {
    id: "authors",
    label: "Authors",
    description: "Navigate the corpus through author-centered groupings.",
  },
  abstracts: {
    id: "abstracts",
    label: "Abstracts",
    description: "Scan available abstracts and expose missing review metadata.",
  },
  search: {
    id: "search",
    label: "Search",
    description: "Search canonical chunks through the Paper KB read service.",
  },
  paper: {
    id: "paper",
    label: "Paper",
    description: "Inspect one paper, its metadata, chunks and bounded derivations.",
  },
};

export const PAPER_CORPUS_WORKBENCH: WorkbenchProduct = {
  id: "paper-corpus-workbench",
  label: "Paper Corpus Workbench",
  description: "A small-corpus research workbench composed from reusable navigation tabs.",
  tabs: ["corpus", "authors", "abstracts", "search", "paper"],
  defaultTab: "corpus",
};

function isWorkbenchTabId(value: string): value is WorkbenchTabId {
  return (WORKBENCH_TAB_IDS as readonly string[]).includes(value);
}

/**
 * Bounded product customization seam.
 *
 * A deployment may choose a subset/order with NEXT_PUBLIC_WORKBENCH_TABS,
 * e.g. "corpus,authors,paper". Unknown/duplicate values are ignored and the
 * canonical Paper KB product remains the fallback. This is deliberately not a
 * plugin system or remote DSL: tabs are code-owned capabilities, while a
 * product is only a selected composition of them.
 */
export function resolveWorkbenchProduct(): WorkbenchProduct {
  const configured = (process.env.NEXT_PUBLIC_WORKBENCH_TABS || "")
    .split(",")
    .map((value) => value.trim())
    .filter((value): value is WorkbenchTabId => Boolean(value) && isWorkbenchTabId(value));

  const tabs = Array.from(new Set(configured));
  if (tabs.length === 0) return PAPER_CORPUS_WORKBENCH;

  return {
    ...PAPER_CORPUS_WORKBENCH,
    id: "configured-paper-workbench",
    tabs,
    defaultTab: tabs.includes(PAPER_CORPUS_WORKBENCH.defaultTab)
      ? PAPER_CORPUS_WORKBENCH.defaultTab
      : tabs[0],
  };
}
