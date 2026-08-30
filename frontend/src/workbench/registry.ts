import type { ComponentType } from "react";
import CorpusTab from "@/components/workbench/tabs/CorpusTab";
import AuthorsTab from "@/components/workbench/tabs/AuthorsTab";
import AbstractsTab from "@/components/workbench/tabs/AbstractsTab";
import SearchTab from "@/components/workbench/tabs/SearchTab";
import PaperTab from "@/components/workbench/tabs/PaperTab";
import type { WorkbenchTabId } from "@/workbench/product";
import type { WorkbenchTabProps } from "@/workbench/types";

export const WORKBENCH_TAB_COMPONENTS: Record<WorkbenchTabId, ComponentType<WorkbenchTabProps>> = {
  corpus: CorpusTab,
  authors: AuthorsTab,
  abstracts: AbstractsTab,
  search: SearchTab,
  paper: PaperTab,
};
