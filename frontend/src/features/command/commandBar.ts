import { createContext, useContext } from "react";

export interface CommandBarValue {
  /** Open the bar, optionally with something already typed. */
  open: (query?: string) => void;
}

export const CommandBarContext = createContext<CommandBarValue>({
  open: () => undefined,
});

/** The one door for anything you can type (Sprint 094). */
export function useCommandBar(): CommandBarValue {
  return useContext(CommandBarContext);
}
