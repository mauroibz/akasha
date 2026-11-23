import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

import { PageFrame } from "@/components/PageFrame";
import { PageHeader } from "@/components/PageHeader";
import { GoalWidget } from "@/features/goals/GoalWidget";
import { EveryDay } from "@/features/journal/EveryDay";
import {
  JournalWidgets,
  type JournalWidget,
} from "@/features/journal/JournalWidgets";
import { PlayWidget } from "@/features/journal/PlayWidget";
import { DiaryPage } from "@/pages/DiaryPage";
import { InsightsPage } from "@/pages/InsightsPage";

const widgets: JournalWidget[] = [
  { id: "day", label: "Every day", render: () => <EveryDay /> },
  { id: "play", label: "Play", render: () => <PlayWidget /> },
  { id: "goal", label: "Goal", render: () => <GoalWidget /> },
];

const section =
  "scroll-mt-6 border-t border-border pt-8 font-display text-3xl font-medium tracking-tight";

/**
 * The Journal (Sprint 146, DEC-193): what was the Diary, Insights and the games, as
 * one place. It opens on something to do, one widget at a time; then what you
 * finished, month by month; then what the library says about you, last. The Diary
 * and Insights are drawn by their own components, without their frames and titles.
 */
export function JournalPage() {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const { hash } = useLocation();
  useEffect(() => {
    // An old address lands on its part of the page (`/diary` on the timeline,
    // `/insights` on the patterns); a plain visit on the page's own heading.
    const target = hash ? document.getElementById(hash.slice(1)) : null;
    if (target) {
      target.scrollIntoView?.();
      target.focus();
    } else headingRef.current?.focus();
  }, [hash]);
  return (
    <PageFrame width="reading" className="pb-24">
      <PageHeader
        headingRef={headingRef}
        title="Journal"
        lede="Something to do, what you finished, and what it says about you."
        className="border-b-0 pb-4"
      />
      <JournalWidgets widgets={widgets} />
      <h2 id="timeline" tabIndex={-1} className={`mt-12 ${section}`}>
        Timeline
      </h2>
      <DiaryPage embedded />
      <h2 id="patterns" tabIndex={-1} className={`mt-16 ${section}`}>
        Patterns
      </h2>
      <InsightsPage embedded />
    </PageFrame>
  );
}
