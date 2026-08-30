import { redirect } from "next/navigation";

export default async function PaperRoute({ params }: { params: Promise<{ paperId: string }> }) {
  const { paperId } = await params;
  redirect(`/?tab=paper&paper=${encodeURIComponent(paperId)}`);
}
