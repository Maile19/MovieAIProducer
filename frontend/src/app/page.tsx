"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/dashboard");
  }, [router]);

  return (
    <div className="min-h-screen w-full bg-canvas flex items-center justify-center text-obsidian-secondary font-mono text-sm">
      Entering Studio Slate...
    </div>
  );
}
