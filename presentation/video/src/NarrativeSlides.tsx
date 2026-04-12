/**
 * NarrativeSlides.tsx
 * Three story slides that open the video before the live demo sequence.
 *
 *  TitleCard    — Brand identity reveal
 *  ProblemSlide — The clinical challenge (3 pain points)
 *  SolutionSlide — The platform architecture (3 agents)
 */
import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { C, FONT, S } from "./constants";

// ── Shared helpers ────────────────────────────────────────────────────────────

function useFadeSlide(enterFrame: number, durationFrames = 25) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const progress = spring({
    frame: frame - enterFrame,
    fps,
    config: { damping: 14, stiffness: 90 },
    durationInFrames: durationFrames,
  });
  return {
    opacity:    interpolate(progress, [0, 1], [0, 1]),
    translateY: interpolate(progress, [0, 1], [32, 0]),
  };
}

const AccentLine: React.FC<{ startFrame: number; color?: string }> = ({
  startFrame,
  color = C.mayo,
}) => {
  const frame = useCurrentFrame();
  const width = interpolate(frame, [startFrame, startFrame + 50], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        height:       4,
        width:        `${width}%`,
        background:   `linear-gradient(to right, ${color}, ${color}88)`,
        borderRadius: 2,
        marginTop:    20,
        marginBottom: 28,
      }}
    />
  );
};

// ── TITLE CARD ────────────────────────────────────────────────────────────────
export const TitleCard: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const iconSpring = spring({ frame, fps, config: { damping: 12, stiffness: 80 }, durationInFrames: 30 });
  const titleSpring = spring({ frame: frame - 12, fps, config: { damping: 14, stiffness: 80 }, durationInFrames: 30 });
  const subSpring   = spring({ frame: frame - 28, fps, config: { damping: 14, stiffness: 80 }, durationInFrames: 30 });
  const chipsSpring = spring({ frame: frame - 44, fps, config: { damping: 14, stiffness: 80 }, durationInFrames: 30 });
  const taglineSpring = spring({ frame: frame - 58, fps, config: { damping: 14, stiffness: 80 }, durationInFrames: 30 });

  const CHIPS = [
    "GPT-4o MDT Roundtable",
    "PubMed Multi-Pillar Search",
    "JCI-Grade Audit Trail",
    "72-Hour Evidence Refinement",
  ];

  return (
    <AbsoluteFill
      style={{
        background:     `radial-gradient(ellipse at 30% 60%, ${C.mayo}44, transparent 55%),
                         linear-gradient(160deg, ${C.darkSlate} 0%, ${C.anthracite} 100%)`,
        display:        "flex",
        flexDirection:  "column",
        alignItems:     "center",
        justifyContent: "center",
        paddingBottom:  S.BAR_H,
      }}
    >
      {/* Icon */}
      <div
        style={{
          fontSize:  140,
          opacity:   iconSpring,
          transform: `scale(${interpolate(iconSpring, [0, 1], [0.6, 1])})`,
          lineHeight: 1,
          marginBottom: 24,
          filter: "drop-shadow(0 0 40px rgba(0,40,104,0.8))",
        }}
      >
        ⚕
      </div>

      {/* Title */}
      <div
        style={{
          fontSize:      S.display,
          fontWeight:    800,
          fontFamily:    FONT,
          color:         C.white,
          letterSpacing: "-0.03em",
          opacity:       titleSpring,
          transform:     `translateY(${interpolate(titleSpring, [0, 1], [24, 0])}px)`,
          textAlign:     "center",
          lineHeight:    1.1,
        }}
      >
        Clinical Intelligence Node
      </div>

      <AccentLine startFrame={20} color={C.mayo} />

      {/* Subtitle */}
      <div
        style={{
          fontSize:   S.subheadline,
          fontFamily: FONT,
          color:      C.mayoLight,
          opacity:    subSpring,
          transform:  `translateY(${interpolate(subSpring, [0, 1], [16, 0])}px)`,
          textAlign:  "center",
          fontWeight: 400,
          maxWidth:   1200,
          lineHeight: 1.4,
        }}
      >
        A virtual 360° MDT Committee Platform · Evidence-Based Clinical Review
      </div>

      {/* Feature chips */}
      <div
        style={{
          display:   "flex",
          gap:       18,
          marginTop: 52,
          opacity:   chipsSpring,
          transform: `translateY(${interpolate(chipsSpring, [0, 1], [16, 0])}px)`,
          flexWrap:  "wrap",
          justifyContent: "center",
        }}
      >
        {CHIPS.map((chip) => (
          <div
            key={chip}
            style={{
              background:    "rgba(0,40,104,0.35)",
              border:        "1.5px solid rgba(0,87,168,0.5)",
              borderRadius:  40,
              padding:       "12px 28px",
              fontSize:      S.caption,
              fontFamily:    FONT,
              color:         C.mayoLight,
              fontWeight:    600,
              letterSpacing: "0.02em",
            }}
          >
            {chip}
          </div>
        ))}
      </div>

      {/* Tagline */}
      <div
        style={{
          marginTop:  52,
          fontSize:   S.label,
          fontFamily: FONT,
          color:      C.midGrey,
          opacity:    taglineSpring * 0.7,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
        }}
      >
        Not a substitute for clinical judgement · All cases fictional
      </div>
    </AbsoluteFill>
  );
};

// ── PROBLEM SLIDE ─────────────────────────────────────────────────────────────
const PAIN_POINTS = [
  {
    icon:  "🏥",
    title: "Evidence is fragmented and time-consuming",
    body:  "Clinicians search PubMed manually. Complex cases hit multiple incomplete literature threads. High-stakes decisions happen without full context.",
    color: C.danger,
  },
  {
    icon:  "⏱",
    title: "Specialist input is delayed or unavailable",
    body:  "MDT meetings require scheduling. Surgical, medical and pharmacy expertise rarely converge in real time. Critical care decisions cannot wait.",
    color: C.warning,
  },
  {
    icon:  "📋",
    title: "No structured governance or audit trail",
    body:  "Verbal decisions leave no traceable rationale. M&M minutes are written retrospectively, inconsistently, and without evidence mapping.",
    color: C.midGrey,
  },
];

export const ProblemSlide: React.FC<{ phaseStart: number }> = ({ phaseStart }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const headerProgress = spring({
    frame: frame - phaseStart,
    fps,
    config: { damping: 14, stiffness: 90 },
    durationInFrames: 25,
  });

  return (
    <AbsoluteFill
      style={{
        background:     `linear-gradient(160deg, #171F27 0%, ${C.darkSlate} 100%)`,
        display:        "flex",
        flexDirection:  "column",
        justifyContent: "center",
        paddingLeft:    120,
        paddingRight:   120,
        paddingBottom:  S.BAR_H + 20,
      }}
    >
      {/* Header */}
      <div
        style={{
          opacity:    interpolate(headerProgress, [0, 1], [0, 1]),
          transform:  `translateY(${interpolate(headerProgress, [0, 1], [20, 0])}px)`,
          marginBottom: 12,
        }}
      >
        <div
          style={{
            fontSize:      S.label,
            fontWeight:    700,
            fontFamily:    FONT,
            color:         C.danger,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            marginBottom:  14,
          }}
        >
          The Challenge
        </div>
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
          Clinical decisions at the intersection<br />of urgency and evidence.
        </div>
      </div>

      <AccentLine startFrame={phaseStart + 5} color={C.danger} />

      {/* Pain points */}
      <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
        {PAIN_POINTS.map((p, i) => {
          const itemProgress = spring({
            frame: frame - phaseStart - 20 - i * 22,
            fps,
            config: { damping: 15, stiffness: 90 },
            durationInFrames: 25,
          });
          return (
            <div
              key={p.title}
              style={{
                display:    "flex",
                gap:        28,
                alignItems: "flex-start",
                opacity:    interpolate(itemProgress, [0, 1], [0, 1]),
                transform:  `translateX(${interpolate(itemProgress, [0, 1], [-40, 0])}px)`,
              }}
            >
              {/* Icon bubble */}
              <div
                style={{
                  width:          80,
                  height:         80,
                  borderRadius:   "50%",
                  background:     `${p.color}18`,
                  border:         `2px solid ${p.color}44`,
                  display:        "flex",
                  alignItems:     "center",
                  justifyContent: "center",
                  fontSize:       38,
                  flexShrink:     0,
                }}
              >
                {p.icon}
              </div>
              <div>
                <div
                  style={{
                    fontSize:   S.bodySmall,
                    fontWeight: 700,
                    fontFamily: FONT,
                    color:      C.white,
                    marginBottom: 8,
                  }}
                >
                  {p.title}
                </div>
                <div
                  style={{
                    fontSize:   S.caption,
                    fontFamily: FONT,
                    color:      C.lightGrey,
                    lineHeight: 1.6,
                    maxWidth:   1100,
                  }}
                >
                  {p.body}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ── SOLUTION SLIDE ────────────────────────────────────────────────────────────
const AGENTS = [
  {
    icon:    "🔬",
    name:    "Researcher",
    model:   "gpt-4o-mini · temp 0.0",
    role:    "Multi-Pillar PubMed Search",
    detail:  "4-tier evidence ladder. Automatic pillar decomposition when evidence is sparse. Guideline anchor via NCCN / AHA / ESC.",
    color:   C.compass,
  },
  {
    icon:    "🏥",
    name:    "MDT Roundtable",
    model:   "gpt-4o · temp 0.25",
    role:    "360° Specialist Debate",
    detail:  "Dynamically selects 4–6 specialists. Each argues from departmental priority. Conflicts become Systemic Gaps. Risk Heatmap output.",
    color:   C.mayo,
  },
  {
    icon:    "📝",
    name:    "Auditor",
    model:   "gpt-4o-mini · temp 0.0",
    role:    "Formal M&M Minutes",
    detail:  "Versioned Markdown minutes. Real PubMed citations only. JCI-grade audit trail with 72-hour automated refinement.",
    color:   C.context,
  },
];

const FEATURES = [
  "25+ Specialties",
  "Critical Gap Detection",
  "Reversal Agent Checks",
  "Cockcroft-Gault CrCl",
  "EPR Copy-Paste Buffer",
  "72-Hour Contradiction Detection",
];

export const SolutionSlide: React.FC<{ phaseStart: number }> = ({ phaseStart }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const headerProgress = spring({
    frame: frame - phaseStart,
    fps,
    config: { damping: 14, stiffness: 90 },
    durationInFrames: 25,
  });

  return (
    <AbsoluteFill
      style={{
        background:     `radial-gradient(ellipse at 70% 30%, ${C.mayo}33, transparent 55%),
                         linear-gradient(160deg, ${C.anthracite} 0%, ${C.darkSlate} 100%)`,
        display:        "flex",
        flexDirection:  "column",
        justifyContent: "center",
        paddingLeft:    100,
        paddingRight:   100,
        paddingBottom:  S.BAR_H + 20,
      }}
    >
      {/* Header */}
      <div
        style={{
          opacity:   interpolate(headerProgress, [0, 1], [0, 1]),
          transform: `translateY(${interpolate(headerProgress, [0, 1], [20, 0])}px)`,
        }}
      >
        <div
          style={{
            fontSize:      S.label,
            fontWeight:    700,
            fontFamily:    FONT,
            color:         C.compass,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            marginBottom:  14,
          }}
        >
          The Solution
        </div>
        <div
          style={{
            fontSize:      S.headline,
            fontWeight:    800,
            fontFamily:    FONT,
            color:         C.white,
            letterSpacing: "-0.02em",
          }}
        >
          One Platform. Three Agents.
        </div>
      </div>

      <AccentLine startFrame={phaseStart + 5} color={C.compass} />

      {/* Agent cards */}
      <div style={{ display: "flex", gap: 28, alignItems: "stretch" }}>
        {AGENTS.map((agent, i) => {
          const cardProgress = spring({
            frame: frame - phaseStart - 18 - i * 18,
            fps,
            config: { damping: 13, stiffness: 80 },
            durationInFrames: 28,
          });

          return (
            <React.Fragment key={agent.name}>
              <div
                style={{
                  flex:         1,
                  background:   `linear-gradient(160deg, ${agent.color}22, ${agent.color}0a)`,
                  border:       `1.5px solid ${agent.color}55`,
                  borderRadius: 16,
                  padding:      "32px 36px",
                  opacity:      interpolate(cardProgress, [0, 1], [0, 1]),
                  transform:    `translateY(${interpolate(cardProgress, [0, 1], [32, 0])}px)`,
                  boxShadow:    `0 12px 40px ${agent.color}22`,
                  position:     "relative",
                  overflow:     "hidden",
                }}
              >
                {/* Top accent */}
                <div
                  style={{
                    position:     "absolute",
                    top:          0,
                    left:         0,
                    right:        0,
                    height:       5,
                    background:   agent.color,
                    borderRadius: "16px 16px 0 0",
                  }}
                />
                <div style={{ fontSize: 60, marginBottom: 20 }}>{agent.icon}</div>
                <div
                  style={{
                    fontSize:   S.bodySmall,
                    fontWeight: 800,
                    fontFamily: FONT,
                    color:      C.white,
                    marginBottom: 6,
                  }}
                >
                  {agent.name}
                </div>
                <div
                  style={{
                    fontSize:      S.micro,
                    fontFamily:    FONT,
                    color:         agent.color,
                    fontWeight:    600,
                    marginBottom:  16,
                    letterSpacing: "0.03em",
                  }}
                >
                  {agent.model}
                </div>
                <div
                  style={{
                    fontSize:   S.caption,
                    fontWeight: 700,
                    fontFamily: FONT,
                    color:      C.white,
                    marginBottom: 10,
                  }}
                >
                  {agent.role}
                </div>
                <div
                  style={{
                    fontSize:   S.micro,
                    fontFamily: FONT,
                    color:      C.lightGrey,
                    lineHeight: 1.6,
                  }}
                >
                  {agent.detail}
                </div>
              </div>

              {/* Arrow connector */}
              {i < AGENTS.length - 1 && (
                <div
                  style={{
                    display:        "flex",
                    alignItems:     "center",
                    justifyContent: "center",
                    flexShrink:     0,
                    opacity: interpolate(cardProgress, [0, 1], [0, 1]),
                  }}
                >
                  <svg width="52" height="52" viewBox="0 0 52 52" fill="none">
                    <path
                      d="M4 26 L40 26 M30 16 L44 26 L30 36"
                      stroke={C.midGrey}
                      strokeWidth="3"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Feature chips */}
      <div
        style={{
          display:        "flex",
          gap:            14,
          marginTop:      32,
          flexWrap:       "wrap",
          justifyContent: "center",
          opacity: interpolate(
            frame,
            [phaseStart + 70, phaseStart + 90],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          ),
        }}
      >
        {FEATURES.map((f) => (
          <div
            key={f}
            style={{
              background:    "rgba(255,255,255,0.06)",
              border:        "1px solid rgba(255,255,255,0.15)",
              borderRadius:  30,
              padding:       "9px 22px",
              fontSize:      S.micro,
              fontFamily:    FONT,
              color:         C.lightGrey,
              fontWeight:    500,
            }}
          >
            ✓ {f}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
