# Validation Rules

This document explains all validation rules active in the African Bamboo
data collection system. Rules are organized by where they run.

## On-Device Rules (ODK App)

These rules run **in real time** during data collection in ODK Collect.
If a rule fails, the submission is **blocked** until corrected.

### Polygon Geometry

| Rule | What It Checks | Failure Trigger |
|------|---------------|-----------------|
| Minimum Vertices | Shape has at least 3 distinct points | Fewer than 3 points drawn |
| Minimum Area | Mapped area is at least 10 m² | Area smaller than 10 square meters |
| No Self-Intersection | Boundary lines do not cross each other | Lines overlap or cross |

### Plot Overlap

| Rule | What It Checks | Failure Trigger |
|------|---------------|-----------------|
| Overlap Detection | New plot does not overlap an existing plot by 20% or more | 20%+ of the smaller plot's area overlaps |

### Image Quality (Blur Detection)

| Rule | What It Checks | Failure Trigger |
|------|---------------|-----------------|
| Image Sharpness | Photo of title deed is readable | Image too blurry to read |

**How blur detection works:**

- The app checks if text in your photo is readable
- **Green (Sharp):** Photo accepted automatically
- **Yellow (Borderline):** Warning shown — you can retake or keep
- **Red (Very Blurry):** Photo rejected — you must retake

> Blur detection thresholds can be adjusted in the app's Settings screen.

## Post-Sync Rules (DCU Dashboard)

These rules run **automatically** when submissions are synced from
KoboToolbox. They generate **warnings** (not rejections) for review.

| # | Rule | Threshold | What It Checks |
|---|------|-----------|---------------|
| W1 | GPS Accuracy Too Low | Average > 15 m | Mean accuracy of GPS points |
| W2 | Point Gap Too Large | Any gap > 50 m | Distance between consecutive vertices |
| W3 | Uneven Point Spacing | CV > 0.5 | Variation in distances between points |
| W4 | Plot Area Too Large | > 20 hectares | Total mapped area |
| W5 | Too Few Vertices | 6-10 vertices | Number of boundary points |

### What do warnings mean?

- Warnings do **not** reject or block submissions
- They flag potential issues for the data manager to review
- A single submission can have multiple warnings
- Warnings appear as amber badges in the DCU Dashboard

## FAQ

**Q: Which rules can I adjust?**

Blur detection thresholds (OCR and Laplacian) can be adjusted in the
ODK app under Settings. All other thresholds are fixed.

**Q: Why was my polygon rejected?**

Check that: (1) you drew at least 3 points, (2) the area is larger
than 10 square meters, and (3) the boundary lines don't cross each other.

**Q: Why was my photo rejected?**

The title deed photo must be clear enough to read. Hold the phone
steady, ensure good lighting, and avoid shadows on the document.

**Q: What does the overlap error mean?**

Your new plot boundary overlaps 20% or more with an existing plot
already in the system. Adjust your boundary to reduce the overlap.
