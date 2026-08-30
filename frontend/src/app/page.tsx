import WorkbenchPage from "@/components/workbench/WorkbenchPage";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function first(value: string | string[] | undefined): string | null {
  if (Array.isArray(value)) return value[0] || null;
  return value || null;
}

export default async function HomePage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  return (
    <WorkbenchPage
      initialTab={first(params.tab)}
      initialPaperId={first(params.paper)}
    />
  );
}
