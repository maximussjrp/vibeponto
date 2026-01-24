import { redirect } from "next/navigation";

export default function Home() {
  // Redireciona para o dashboard ou login
  redirect("/login");
}
