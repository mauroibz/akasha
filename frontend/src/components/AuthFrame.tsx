import type { ReactNode } from "react";

import { AkashaMark } from "@/components/AkashaMark";
import { Panel } from "@/components/Panel";

export function AuthFrame({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center text-center">
          <AkashaMark size={56} className="text-foreground" />
          <h1 className="mt-4 text-4xl font-semibold tracking-tight">Akasha</h1>
        </div>
        <Panel className="mt-8" bodyClassName="p-5 sm:p-6">
          {children}
        </Panel>
      </div>
    </main>
  );
}
