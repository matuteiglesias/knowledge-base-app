import { redirect } from "next/navigation";

export default function LegacyChunksHealthRoute() {
  redirect("/?tab=corpus");
}
