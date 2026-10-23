/** Long titles step down, so the whole of one fits where a short one is set large. */
export function titleSize(title: string) {
  if (title.length <= 40) return "text-3xl md:text-5xl";
  if (title.length <= 80) return "text-2xl md:text-4xl";
  return "text-xl md:text-3xl";
}
