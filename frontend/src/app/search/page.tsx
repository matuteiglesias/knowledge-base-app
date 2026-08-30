import { redirect } from "next/navigation";

export default function LegacySearchRoute() {
  redirect("/?tab=search");
}
