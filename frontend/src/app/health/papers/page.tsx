import { redirect } from "next/navigation";

export default function LegacyPapersHealthRoute() {
  redirect("/?tab=corpus");
}
