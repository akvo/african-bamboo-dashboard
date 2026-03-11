# User Acceptance Criteria

> **Note:** Consider collecting names in Geʽez script?

Select a plot, see title deed next to names and other identifying info, click accept or reject or allow name correction if difference is very small.

---

## User Stories

**As a user**
Given a plot has a title deed image uploaded
When I click "See data" next to the Title Deed field
Then the title deed image is displayed in a side panel or modal
And the plot details remain visible on the left
And I can visually compare the image with the plot data

**As a user**
Given the title deed image is open
When I click the Close (X) button
Then the image panel closes
And I remain on the same plot details screen

**As a user**
Given the title deed image is open
When the image loads
Then it is displayed in full resolution
And it is not distorted
And it fits within the available viewport

**As a user**
Given no title deed image was uploaded
When I view the plot details
Then a message indicates "No title deed uploaded"

**As a user**
Given multiple title deed images exist
When I open the title deed viewer
Then I can navigate between images
And the current image index is visible

---

## Functional Requirements

The system shall:

- Display a clickable "See data" action next to the Title Deed field if an image exists.
- Open the image in an overlay, side panel, or modal.
- Keep the plot data panel visible for comparison.
- Allow the user to close the image viewer.
- Support common image formats (JPG, PNG).
- Maintain the current plot state while the image is open.
- Prevent unintended navigation away from the plot.

---

## Non-Functional Requirements

### Performance
- Image must load within 2 seconds under normal network conditions.
- Large images must be optimized for fast rendering.

### Usability
- Image must scale proportionally.
- The user must be able to clearly read text on the title deed.
- Layout must allow side-by-side comparison without horizontal scrolling (minimum 1280px width).

### Accessibility
- Close button must be keyboard accessible (`Esc`).

---

## Error Handling

### Image Fails to Load
- Display placeholder message: *"Unable to load title deed image."*
- Provide retry option.
- Do not break the plot details screen.