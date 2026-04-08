function formatDate(isoString) {
  if (!isoString) {return null;}
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) {return isoString;}
    return date.toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return isoString;
  }
}

export function extractPlotDetails(submission) {
  const mapped = submission?.field_mapped_data || {};
  const getValue = (key) => mapped[key]?.value ?? null;
  const getRawValue = (key) => mapped[key]?.raw_value ?? null;

  const allAttachments = submission?.attachments || [];

  return {
    region: getValue("region"),
    area: submission?.area_ha != null ? String(submission.area_ha) : null,
    woreda: getValue("woreda"),
    startDate: formatDate(getValue("start_date")),
    endDate: formatDate(getValue("end_date")),
    enumerator: {
      name: getValue("enumerator"),
      idNumber: getRawValue("enumerator"),
    },
    farmer: {
      name: getValue("farmer"),
      fatherName: getValue("father_name"),
      grandfatherName: getValue("grandfather_name"),
    },
    titleDeed: getValue("title_deed"),
    notes: submission?.rejection_reason,
    attachments: allAttachments,
  };
}
