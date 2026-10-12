// Region picker options from every form's filter_options,
// one per stored code. Each form codes the same region
// differently (spec D-8), so the label names the form.
export function mergeRegionOptions(perForm) {
  const byValue = new Map();
  for (const { formName, regions } of perForm) {
    for (const { value, label } of regions) {
      if (!byValue.has(value)) {
        byValue.set(value, {
          value,
          label: `${label} — ${formName} (${value})`,
          badge: `${label} (${value})`,
        });
      }
    }
  }
  return [...byValue.values()];
}

// Options no configured group covers. An All regions
// group (regions: []) covers everything.
export function uncoveredRegions(options, groups) {
  const active = groups.filter((g) => g.chat_id);
  if (active.some((g) => g.regions.length === 0)) {
    return [];
  }
  const covered = new Set(active.flatMap((g) => g.regions));
  return options.filter((o) => !covered.has(o.value));
}
