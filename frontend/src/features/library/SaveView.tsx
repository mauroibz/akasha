import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bookmark } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { queryKeys } from "@/api/keys";
import { saveView } from "@/api/views";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

/**
 * Names the library's current filters (Sprint 100). `query` is the library's own
 * URL query, so reopening the view is navigating back to it; saving under a name
 * already used replaces what that name opens.
 */
export function SaveView({ query }: { query: string }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const save = useMutation({
    mutationFn: () => saveView(name.trim(), query),
    onSuccess: (view) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.views });
      toast.success(`Saved “${view.name}”. Find it in the command bar.`);
      setOpen(false);
      setName("");
    },
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : "The view could not be saved",
      ),
  });

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="ghost" className="min-h-11 gap-2">
          <Bookmark className="h-4 w-4" aria-hidden="true" />
          Save view
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72">
        <form
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (name.trim()) save.mutate();
          }}
        >
          <label htmlFor="save-view-name" className="text-sm font-medium">
            View name
          </label>
          <Input
            id="save-view-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Unread sci-fi"
            maxLength={120}
            autoFocus
          />
          <Button type="submit" disabled={!name.trim() || save.isPending}>
            Save
          </Button>
        </form>
      </PopoverContent>
    </Popover>
  );
}
