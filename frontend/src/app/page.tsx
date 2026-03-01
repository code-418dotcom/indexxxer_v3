import { redirect } from "next/navigation";

/**
 * Root page — immediately redirects to the media library.
 * This keeps the library as the canonical home without a pointless landing page.
 */
export default function Home() {
  redirect("/library");
}
