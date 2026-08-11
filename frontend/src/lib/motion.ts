import { useMemo } from "react";
import { useReducedMotion } from "motion/react";
import type { Target, TargetAndTransition, Variants } from "motion/react";

/**
 * Every duration and easing in the application, in one place.
 *
 * Two rules make the motion layer reviewable rather than a scatter of magic
 * numbers. A component asks this module for its values and never writes a
 * `transition` literal; and every preset is built in both a full and a reduced
 * form here, so respecting `prefers-reduced-motion` is a property of the
 * construction rather than something each new surface has to remember.
 *
 * The `index.css` `prefers-reduced-motion` block remains the CSS-level
 * backstop. It cannot help here: Motion drives the Web Animations API and
 * inline styles, which no stylesheet can override.
 */
export const motionDuration = {
  /** Leaving: shorter than arriving, so a swap does not feel like a pause. */
  fast: 0.12,
  base: 0.18,
  panel: 0.14,
  form: 0.2,
  bar: 0.16,
  /** Per-item step in a staggered list. */
  stagger: 0.03,
} as const;

/**
 * Past this many items the delay stops growing. A 30-result search would
 * otherwise take almost a second to finish arriving, which reads as slow
 * rather than as considered.
 */
const staggerClamp = 8;

const easeOut = [0.22, 1, 0.36, 1] as const;

/** An enter (and optionally exit) preset, spread straight onto an `m` element. */
export interface EnterPreset {
  initial: false | Target;
  animate: TargetAndTransition;
  exit?: TargetAndTransition;
}

export interface MotionPresets {
  readonly reduced: boolean;
  /** The library list container, keyed on sort and filter. */
  readonly crossfade: Required<EnterPreset>;
  /** The score picker's expanded panel. Enter only, by design. */
  readonly panel: EnterPreset;
  /** The add form replacing the search results. */
  readonly formEnter: EnterPreset;
  /** The triage bulk action bar. Transform only: it sits in normal flow. */
  readonly actionBar: EnterPreset;
  /** A committed score: set `from`, then spring `to`. */
  readonly commitPop: { from: false | Target; to: TargetAndTransition };
  /** `whileTap` on a control that commits a value. */
  readonly press: TargetAndTransition;
  readonly staggerItem: (index: number) => Variants;
}

const still = { transition: { duration: 0 } } as const;

function fullMotion(): Omit<MotionPresets, "reduced"> {
  return {
    crossfade: {
      initial: { opacity: 0 },
      animate: {
        opacity: 1,
        transition: { duration: motionDuration.base, ease: easeOut },
      },
      exit: {
        opacity: 0,
        transition: { duration: motionDuration.fast, ease: "easeIn" },
      },
    },
    panel: {
      initial: { opacity: 0, scale: 0.96, y: 4 },
      animate: {
        opacity: 1,
        scale: 1,
        y: 0,
        transition: { duration: motionDuration.panel, ease: easeOut },
      },
    },
    formEnter: {
      initial: { opacity: 0, y: 10 },
      animate: {
        opacity: 1,
        y: 0,
        transition: { duration: motionDuration.form, ease: easeOut },
      },
    },
    actionBar: {
      initial: { opacity: 0, y: -8 },
      animate: {
        opacity: 1,
        y: 0,
        transition: { duration: motionDuration.bar, ease: easeOut },
      },
    },
    // Overshoot and settle. The trigger is the element that survives the
    // commit; the panel unmounts in the same tick, so animating the panel here
    // would animate a corpse.
    commitPop: {
      from: { scale: 1.12 },
      to: {
        scale: 1,
        transition: { type: "spring", stiffness: 520, damping: 13, mass: 0.6 },
      },
    },
    press: { scale: 0.96 },
    staggerItem: (index: number) => ({
      hidden: { opacity: 0, y: 6 },
      show: {
        opacity: 1,
        y: 0,
        transition: {
          duration: motionDuration.base,
          ease: easeOut,
          delay: Math.min(index, staggerClamp) * motionDuration.stagger,
        },
      },
    }),
  };
}

function reducedMotion(): Omit<MotionPresets, "reduced"> {
  // `initial: false` rather than a zero-duration transform: a transform that
  // starts off-target is a visible jump on the first painted frame no matter
  // how short the animation is.
  return {
    crossfade: { initial: false, animate: { opacity: 1, ...still }, exit: {} },
    panel: { initial: false, animate: { opacity: 1, ...still } },
    formEnter: { initial: false, animate: { opacity: 1, ...still } },
    actionBar: { initial: false, animate: { opacity: 1, ...still } },
    commitPop: { from: false, to: { ...still } },
    press: {},
    staggerItem: () => ({
      hidden: { opacity: 1 },
      show: { opacity: 1, transition: { duration: 0, delay: 0 } },
    }),
  };
}

export function useMotionPresets(): MotionPresets {
  const reduced = useReducedMotion() ?? false;
  return useMemo(
    () => ({ reduced, ...(reduced ? reducedMotion() : fullMotion()) }),
    [reduced],
  );
}
