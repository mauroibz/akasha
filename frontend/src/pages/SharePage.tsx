import { useEffect } from "react";
import { Navigate, useSearchParams } from "react-router-dom";

import { useCommandBar } from "@/features/command/commandBar";
import { sharedValue } from "@/features/command/share";

/**
 * Where a phone's share sheet lands (Sprint 097, the manifest's share_target): what
 * was shared opens in the command bar over the library, already resolving.
 */
export function SharePage() {
  const [params] = useSearchParams();
  const { open } = useCommandBar();
  const value = sharedValue(params);
  useEffect(() => {
    open(value);
  }, [open, value]);
  return <Navigate to="/" replace />;
}
