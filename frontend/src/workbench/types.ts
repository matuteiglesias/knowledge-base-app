import type { CorpusHealthResponse, CorpusInfoResponse } from "@/api/types";
import type { PaperMeta } from "@/lib/normalizers";
import type { WorkbenchTabId } from "@/workbench/product";

export type WorkbenchNavigate = (tab: WorkbenchTabId, paperId?: string | null) => void;

export type WorkbenchTabProps = {
  papers: PaperMeta[];
  selectedPaper: PaperMeta | null;
  corpusInfo: CorpusInfoResponse | null;
  corpusHealth: CorpusHealthResponse | null;
  navigate: WorkbenchNavigate;
};
