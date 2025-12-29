import React from "react";
import { Meta, StoryFn } from "@storybook/react";
import PaperList from "@/components/presentational/PaperList";
import type { PaperMeta } from "@/api/types";

export default {
  title: "PaperList",
  component: PaperList,
} as Meta;

const samplePapers: PaperMeta[] = [
  { paperId: "p1", title: "Paper One", authors: ["A. Author"], nChunks: 3, preview: "short preview" },
  { paperId: "p2", title: "Second Paper", authors: ["B. Writer"], nChunks: 5 },
];

const Template: StoryFn = (args) => <PaperList {...args} />;

export const Empty = Template.bind({});
Empty.args = { papers: [], onOpen: () => {}, onSelect: () => {} };

export const WithItems = Template.bind({});
WithItems.args = { papers: samplePapers, onOpen: (p) => console.log("open", p.paperId), onSelect: (p) => console.log("select", p.paperId) };
