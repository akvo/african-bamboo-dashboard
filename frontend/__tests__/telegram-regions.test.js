import {
  mergeRegionOptions,
  uncoveredRegions,
} from "../src/lib/telegram-regions";

const perForm = [
  {
    formName: "Parcel",
    regions: [
      { value: "ORO", label: "Oromia" },
      { value: "SID", label: "Sidama" },
    ],
  },
  {
    formName: "Clone",
    regions: [
      { value: "ET16", label: "Sidama" },
      { value: "ORO", label: "Oromia" },
    ],
  },
];

describe("mergeRegionOptions", () => {
  it("keeps one entry per code, labelled with its form", () => {
    expect(mergeRegionOptions(perForm)).toEqual([
      { value: "ORO", label: "Oromia — Parcel (ORO)", badge: "Oromia (ORO)" },
      { value: "SID", label: "Sidama — Parcel (SID)", badge: "Sidama (SID)" },
      { value: "ET16", label: "Sidama — Clone (ET16)", badge: "Sidama (ET16)" },
    ]);
  });
});

describe("uncoveredRegions", () => {
  const options = mergeRegionOptions(perForm);
  const values = (list) => list.map((o) => o.value);

  it("lists every region when there are no groups", () => {
    expect(values(uncoveredRegions(options, []))).toEqual([
      "ORO",
      "SID",
      "ET16",
    ]);
  });

  it("lists nothing when an All regions group exists", () => {
    const groups = [{ chat_id: "-1", regions: [] }];
    expect(uncoveredRegions(options, groups)).toEqual([]);
  });

  it("lists regions no scoped group covers", () => {
    const groups = [{ chat_id: "-1", regions: ["ORO", "SID"] }];
    expect(values(uncoveredRegions(options, groups))).toEqual(["ET16"]);
  });

  it("ignores rows with no chat yet", () => {
    const groups = [{ chat_id: "", regions: [] }];
    expect(values(uncoveredRegions(options, groups))).toHaveLength(3);
  });
});
