const FlagType = {
  // Geometry errors (existing)
  GEOMETRY_NO_DATA: "GEOMETRY_NO_DATA",
  GEOMETRY_PARSE_FAIL: "GEOMETRY_PARSE_FAIL",
  GEOMETRY_TOO_FEW_VERTICES: "GEOMETRY_TOO_FEW_VERTICES",
  GEOMETRY_SELF_INTERSECT: "GEOMETRY_SELF_INTERSECT",
  GEOMETRY_AREA_TOO_SMALL: "GEOMETRY_AREA_TOO_SMALL",
  // Overlap (existing)
  OVERLAP: "OVERLAP",
  // Warnings (new — W1–W5)
  GPS_ACCURACY_LOW: "GPS_ACCURACY_LOW",
  POINT_GAP_LARGE: "POINT_GAP_LARGE",
  POINT_SPACING_UNEVEN: "POINT_SPACING_UNEVEN",
  AREA_TOO_LARGE: "AREA_TOO_LARGE",
  VERTICES_TOO_FEW_ROUGH: "VERTICES_TOO_FEW_ROUGH",
};

const FlagSeverity = {
  ERROR: "error",
  WARNING: "warning",
};

const FlagMessages = {
  [FlagType.GEOMETRY_NO_DATA]: "No geometry data provided.",
  [FlagType.GEOMETRY_PARSE_FAIL]: "Failed to parse geometry data.",
  [FlagType.GEOMETRY_TOO_FEW_VERTICES]: "Geometry has too few vertices.",
  [FlagType.GEOMETRY_SELF_INTERSECT]: "Geometry is self-intersecting.",
  [FlagType.GEOMETRY_AREA_TOO_SMALL]: "Geometry area is too small.",
  [FlagType.OVERLAP]: "Plot overlap detected.",
  [FlagType.GPS_ACCURACY_LOW]: "Average GPS accuracy > 15m",
  [FlagType.POINT_GAP_LARGE]: "Gap between consecutive polygon points > 50m.",
  [FlagType.POINT_SPACING_UNEVEN]:
    "Uneven point spacing (Coefficient of Variation of point spacing > 0.5).",
  [FlagType.AREA_TOO_LARGE]: "Plot area > 20 ha.",
  [FlagType.VERTICES_TOO_FEW_ROUGH]:
    "Polygon contains only 6–10 vertices (boundary may be too rough).",
};

/**
 * Parse flagged_reason (JSON array or legacy string) into a list of flags.
 */
function parseFlags(flaggedReason) {
  if (Array.isArray(flaggedReason)) return flaggedReason;
  return [];
}

/**
 * Split flags by severity.
 */
function splitFlags(flaggedReason) {
  const flags = parseFlags(flaggedReason);
  return {
    errors: flags.filter((f) => f.severity === FlagSeverity.ERROR),
    warnings: flags.filter((f) => f.severity === FlagSeverity.WARNING),
  };
}

export { FlagType, FlagSeverity, FlagMessages, parseFlags, splitFlags };
