import { redirect } from "next/navigation";

export default function LegacyTopicsRoute() {
  redirect("/?tab=corpus");
}
