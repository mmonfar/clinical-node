// ── Timing ───────────────────────────────────────────────────────────────────
export const FPS           = 30;
export const TOTAL_FRAMES  = 1680;  // 56 seconds — extended for readable speech bubbles

/**
 * Phase start/end in frames at 30 fps.
 *
 * Phases 0-2 are narrative story slides.
 * Phases 3-6 are the live demo sequence.
 *
 * CLASH is extended to 680 frames so all 6 speech bubbles appear
 * sequentially (75 frames / 2.5 s each) with no overlap.
 */
export const PHASES = {
  TITLE:          { start: 0,    end: 120  }, // 0 – 4 s    Title card
  PROBLEM:        { start: 120,  end: 280  }, // 4 – 9.3 s  The challenge
  SOLUTION:       { start: 280,  end: 440  }, // 9.3 – 14.7 s The platform
  EVIDENCE_SCAN:  { start: 440,  end: 560  }, // 14.7 – 18.7 s Researcher
  MATRIX:         { start: 560,  end: 760  }, // 18.7 – 25.3 s Evidence Matrix
  CLASH:          { start: 760,  end: 1440 }, // 25.3 – 48 s   MDT Roundtable (680 frames)
  GOVERNANCE:     { start: 1440, end: 1680 }, // 48 – 56 s     Governance / Audit
} as const;

// ── Scale constants — tuned for 1920 × 1080 ──────────────────────────────────
export const S = {
  // Typography
  display:       120,
  headline:       80,
  subheadline:    52,
  body:           36,
  bodySmall:      28,
  caption:        24,
  label:          20,
  micro:          17,

  // Roundtable spatial
  TABLE_RADIUS:   320,
  TABLE_D:        480,
  AVATAR_D:       140,
  AVATAR_ICON:     68,
  SPEECH_W:       360,

  // Panel widths
  PILLAR_W:       500,
  RISK_PANEL_W:   560,
  REC_PANEL_W:    560,
  SEAL_SIZE:      300,

  // Branding bar
  BAR_H:           80,
} as const;

// ── Palette ───────────────────────────────────────────────────────────────────
export const C = {
  anthracite: "#2C3E50",
  darkSlate:  "#1A252F",
  tableTop:   "#243342",
  mayo:       "#002868",
  mayoLight:  "#D6E0F5",
  gold:       "#002868",
  goldBg:     "#0A3875",
  compass:    "#1E8449",
  compassBg:  "#174D34",
  context:    "#C87400",
  contextBg:  "#5C3600",
  white:      "#FFFFFF",
  lightGrey:  "#B0BCCF",
  midGrey:    "#718BA8",
  verified:   "#1E8449",
  danger:     "#C0392B",
  warning:    "#E67E22",
  surgical:   "#0057A8",
  medical:    "#1E8449",
  support:    "#8E44AD",
} as const;

export const FONT = "'Inter', 'Roboto', 'Helvetica Neue', sans-serif";

// ── MDT Specialists (roundtable cast) ────────────────────────────────────────
export interface Specialist {
  name:      string;
  category:  "Surgical" | "Medical" | "Support";
  color:     string;
  priority:  string;
  statement: string;
}

export const ROUNDTABLE_CAST: Specialist[] = [
  {
    name:      "ICU / Intensivist",
    category:  "Support",
    color:     C.support,
    priority:  "Haemodynamic stability",
    statement: "Bowel viability window is closing. Revascularisation within 6 h or resection is inevitable.",
  },
  {
    name:      "Vascular Surgery",
    category:  "Surgical",
    color:     C.surgical,
    priority:  "Revascularisation",
    statement: "SMA thrombosis confirmed. IR thrombolysis is the bridge to patency — DAPT must pause.",
  },
  {
    name:      "Cardiology",
    category:  "Medical",
    color:     C.medical,
    priority:  "Stent thrombosis risk",
    statement: "DES placed 4 days ago. DAPT interruption risks acute in-stent thrombosis. Mortality 20–40%.",
  },
  {
    name:      "Clinical Pharmacy",
    category:  "Support",
    color:     C.support,
    priority:  "Reversal & dosing",
    statement: "Andexanet alfa if Xa-inhibitor on board. CrCl required before any re-dosing.",
  },
  {
    name:      "General Surgery",
    category:  "Surgical",
    color:     C.surgical,
    priority:  "Surgical contingency",
    statement: "Prepare OR for damage-control laparotomy if IR fails. Bowel resection as fallback.",
  },
  {
    name:      "Hematology",
    category:  "Medical",
    color:     C.medical,
    priority:  "Coagulopathy",
    statement: "Bridge with UFH 48 h post-intervention. Target INR 1.8–2.2 before any procedure.",
  },
];

// ── Evidence pillars ──────────────────────────────────────────────────────────
export interface Pillar {
  id:       "A" | "B" | "C";
  icon:     string;
  label:    string;
  sublabel: string;
  tier:     string;
  articles: number;
  color:    string;
  bg:       string;
  hasGap:   boolean;
}

export const PILLARS: Pillar[] = [
  {
    id:       "A",
    icon:     "🥇",
    label:    "Conflict Intersection",
    sublabel: "Mesenteric Ischaemia AND DAPT",
    tier:     "Case Reports",
    articles: 2,
    color:    C.gold,
    bg:       C.goldBg,
    hasGap:   true,
  },
  {
    id:       "B",
    icon:     "🧭",
    label:    "Primary Guidelines",
    sublabel: "Acute Mesenteric Ischaemia",
    tier:     "Practice Guidelines",
    articles: 5,
    color:    C.compass,
    bg:       C.compassBg,
    hasGap:   false,
  },
  {
    id:       "C",
    icon:     "📋",
    label:    "Procedural Evidence",
    sublabel: "IR thrombolysis mesenteric",
    tier:     "Observational Studies",
    articles: 3,
    color:    C.context,
    bg:       C.contextBg,
    hasGap:   false,
  },
];
