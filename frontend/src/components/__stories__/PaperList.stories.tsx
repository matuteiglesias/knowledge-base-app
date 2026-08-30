import type { Meta, StoryObj } from "@storybook/react";
import PaperList from "@/components/presentational/PaperList";
import type { PaperMeta } from "@/lib/normalizers";

const samplePapers: PaperMeta[] = [
  {
    paperId: "paper_demo_1",
    paperUid: "paper_demo_1",
    title: "Paper One",
    authors: ["A. Author"],
    nChunks: 3,
    preview: "short preview",
    tags: [],
  },
  {
    paperId: "paper_demo_2",
    paperUid: "paper_demo_2",
    title: "Second Paper",
    authors: ["B. Writer"],
    nChunks: 5,
    tags: [],
  },
];

const meta = {
  title: "Workbench/PaperList",
  component: PaperList,
  args: {
    onOpen: () => undefined,
    onSelect: () => undefined,
  },
} satisfies Meta<typeof PaperList>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Empty: Story = {
  args: { papers: [] },
};

export const WithItems: Story = {
  args: { papers: samplePapers },
};
