import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { C, FONT, S, PHASES } from "./constants";
import { TitleCard, ProblemSlide, SolutionSlide } from "./NarrativeSlides";
import { EvidenceMatrix } from "./EvidenceMatrix";
import { Roundtable } from "./Roundtable";
import { MicroscopeIcon } from "./Icons";

// ── Phase label (top-left corner overlay) ─────────────────────────────────────
const PhaseLabel: React.FC<{ label: string; sub: string; enterFrame: number }> = ({
  label, sub, enterFrame,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const progress = spring({
    frame: frame - enterFrame,
    fps,
    config: { damping: 14, stiffness: 100 },
    durationInFrames: 22,
  });
  return (
    <div
      style={{
        position:  "absolute",
        top:       44,
        left:      80,
        opacity:   interpolate(progress, [0, 1], [0, 1]),
        transform: `translateY(${interpolate(progress, [0, 1], [-14, 0])}px)`,
        zIndex:    50,
      }}
    >
      <div
        style={{
          fontSize:      S.label,
          fontWeight:    700,
          fontFamily:    FONT,
          color:         C.mayoLight,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          opacity:       0.65,
          marginBottom:  5,
        }}
      >
        {sub}
      </div>
      <div
        style={{
          fontSize:      S.subheadline,
          fontWeight:    800,
          fontFamily:    FONT,
          color:         C.white,
          letterSpacing: "-0.01em",
        }}
      >
        {label}
      </div>
    </div>
  );
};

// ── Persistent branding bar ────────────────────────────────────────────────────
const BrandingBar: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 22], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <div
      style={{
        position:    "absolute",
        bottom:      0,
        left:        0,
        right:       0,
        height:      S.BAR_H,
        background:  "linear-gradient(to right, rgba(0,40,104,0.96), rgba(0,40,104,0.65))",
        borderTop:   "1px solid rgba(255,255,255,0.08)",
        display:     "flex",
        alignItems:  "center",
        paddingLeft: 80,
        paddingRight:80,
        gap:         20,
        opacity,
        zIndex:      100,
      }}
    >
      <span style={{ fontSize: 30 }}>⚕</span>
      <div>
        <span style={{ fontSize: S.bodySmall, fontWeight: 700, fontFamily: FONT, color: C.white }}>
          Clinical Intelligence Node
        </span>
        <span style={{ fontSize: S.label, fontFamily: FONT, color: C.mayoLight, opacity: 0.65, marginLeft: 16 }}>
          360° Virtual MDT · Evidence-Based Clinical Review · JCI-Grade Audit
        </span>
      </div>
      <div style={{ flex: 1 }} />
      <div style={{ fontSize: S.micro, fontFamily: FONT, color: C.lightGrey, opacity: 0.45 }}>
        ⚠ All cases fictional · Not a substitute for clinical judgement
      </div>
    </div>
  );
};

// ── Evidence Scan phase ────────────────────────────────────────────────────────
const EvidenceScanPhase: React.FC<{ phaseStart: number }> = ({ phaseStart }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const pulse     = 1 + 0.07 * Math.sin((frame * Math.PI) / 12);
  const titleProg = spring({ frame: frame - phaseStart - 8,  fps, config: { damping: 14, stiffness: 80 }, durationInFrames: 28 });
  const subProg   = spring({ frame: frame - phaseStart - 22, fps, config: { damping: 14, stiffness: 80 }, durationInFrames: 28 });

  const STEPS = [
    "Extracting SBAR components from clinical narrative...",
    "Building focused MeSH-compatible PubMed query...",
    "Executing Multi-Pillar search — Conflict · Guidelines · Procedure...",
  ];

  return (
    <AbsoluteFill
      style={{
        display:        "flex",
        flexDirection:  "column",
        alignItems:     "center",
        justifyContent: "center",
        paddingBottom:  S.BAR_H,
        gap:            44,
      }}
    >
      {/* Pulsing microscope */}
      <div style={{ transform: `scale(${pulse})`, filter: "drop-shadow(0 0 30px rgba(0,40,104,0.7))" }}>
        <MicroscopeIcon size={130} color={C.white} />
      </div>

      {/* Headline */}
      <div
        style={{
          textAlign:  "center",
          opacity:    interpolate(titleProg, [0, 1], [0, 1]),
          transform:  `translateY(${interpolate(titleProg, [0, 1], [20, 0])}px)`,
        }}
      >
        <div
          style={{
            fontSize:      S.headline,
            fontWeight:    800,
            fontFamily:    FONT,
            color:         C.white,
            letterSpacing: "-0.02em",
            lineHeight:    1.15,
          }}
        >
          Deconstructing the Case
        </div>
        <div style={{ fontSize: S.subheadline * 0.75, fontFamily: FONT, color: C.mayoLight, marginTop: 10 }}>
          via Multi-Pillar PubMed Search
        </div>
      </div>

      {/* Step list */}
      <div
        style={{
          display:       "flex",
          flexDirection: "column",
          gap:           20,
          alignItems:    "flex-start",
          opacity:       interpolate(subProg, [0, 1], [0, 1]),
        }}
      >
        {STEPS.map((step, i) => {
          const stepOpacity = interpolate(frame,
            [phaseStart + 22 + i * 18, phaseStart + 36 + i * 18],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );
          return (
            <div key={step} style={{ display: "flex", alignItems: "center", gap: 18, opacity: stepOpacity }}>
              <div style={{ width: 14, height: 14, borderRadius: "50%", background: C.compass, flexShrink: 0 }} />
              <div style={{ fontSize: S.body * 0.85, fontFamily: FONT, color: C.lightGrey }}>{step}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ── Root composition ──────────────────────────────────────────────────────────
export const HODCommittee: React.FC = () => {
  const frame = useCurrentFrame();

  const isTitle   = frame < PHASES.PROBLEM.start;
  const isProblem = frame >= PHASES.PROBLEM.start  && frame < PHASES.SOLUTION.start;
  const isSolution= frame >= PHASES.SOLUTION.start && frame < PHASES.EVIDENCE_SCAN.start;
  const isScan    = frame >= PHASES.EVIDENCE_SCAN.start && frame < PHASES.MATRIX.start;
  const isMatrix  = frame >= PHASES.MATRIX.start   && frame < PHASES.CLASH.start;
  const isClash   = frame >= PHASES.CLASH.start    && frame < PHASES.GOVERNANCE.start;
  const isGov     = frame >= PHASES.GOVERNANCE.start;

  const bgColor =
    isTitle    ? C.darkSlate :
    isProblem  ? "#171F27"   :
    isSolution ? C.anthracite:
    C.anthracite;

  return (
    <AbsoluteFill style={{ background: bgColor, overflow: "hidden" }}>

      {isTitle && <TitleCard />}

      {isProblem && <ProblemSlide phaseStart={PHASES.PROBLEM.start} />}

      {isSolution && <SolutionSlide phaseStart={PHASES.SOLUTION.start} />}

      {isScan && (
        <>
          <PhaseLabel label="Researcher Agent" sub="Phase I · Evidence Scan" enterFrame={PHASES.EVIDENCE_SCAN.start} />
          <EvidenceScanPhase phaseStart={PHASES.EVIDENCE_SCAN.start} />
        </>
      )}

      {isMatrix && (
        <>
          <PhaseLabel label="Evidence Matrix" sub="Phase II · PubMed Results" enterFrame={PHASES.MATRIX.start} />
          <EvidenceMatrix startFrame={PHASES.MATRIX.start} />
        </>
      )}

      {(isClash || isGov) && (
        <>
          <PhaseLabel
            label={isGov ? "Governance & Audit" : "MDT Roundtable"}
            sub={isGov ? "Phase IV · M&M Minutes" : "Phase III · The Clash"}
            enterFrame={isGov ? PHASES.GOVERNANCE.start : PHASES.CLASH.start}
          />
          <Roundtable />
        </>
      )}

      <BrandingBar />
    </AbsoluteFill>
  );
};
