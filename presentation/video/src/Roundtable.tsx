import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { C, FONT, S, PHASES, ROUNDTABLE_CAST } from "./constants";
import { HOD_Avatar } from "./HOD_Avatar";
import { VerifiedSeal } from "./Icons";

// 6 specialists at equal angles
const AVATAR_ANGLES = [0, 60, 120, 180, 240, 300];

// All frame offsets are relative to PHASES.CLASH.start so speed changes
// only require updating constants.ts — nothing here breaks.
const CS = PHASES.CLASH.start;
const GS = PHASES.GOVERNANCE.start;

// Avatar entry: stagger every ~27 frames (scaled from 20)
const ENTER_FRAMES  = [CS + 3,  CS + 30, CS + 57, CS + 84, CS + 111, CS + 138];

// Speech bubble appearances: staggered across the clash phase
const BUBBLE_FRAMES = [CS + 40, CS + 93, CS + 147, CS + 200, CS + 27, CS + 120];

const RISKS = [
  { label: "In-stent thrombosis",           level: "High",   color: C.danger  },
  { label: "Bowel infarction",              level: "High",   color: C.danger  },
  { label: "Anticoagulant reversal window", level: "High",   color: C.danger  },
  { label: "CrCl-dependent drug dosing",    level: "Medium", color: C.warning },
  { label: "Surgical site bleeding",        level: "Medium", color: C.warning },
  { label: "Anaesthetic induction risk",    level: "Low",    color: C.verified},
];

// ── Circular table ────────────────────────────────────────────────────────────
const CircularTable: React.FC = () => (
  <div
    style={{
      position:     "absolute",
      left:         "50%",
      top:          "50%",
      transform:    "translate(-50%, -50%)",
      width:        S.TABLE_D,
      height:       S.TABLE_D,
      borderRadius: "50%",
      background:   `radial-gradient(circle, ${C.tableTop} 55%, ${C.anthracite} 100%)`,
      border:       "3px solid rgba(255,255,255,0.1)",
      boxShadow:    "0 0 80px rgba(0,40,104,0.55)",
      display:      "flex",
      alignItems:   "center",
      justifyContent: "center",
      flexDirection:  "column",
      gap:          8,
    }}
  >
    <span style={{ fontSize: 64 }}>⚕</span>
    <div
      style={{
        fontSize:      S.label,
        fontWeight:    700,
        fontFamily:    FONT,
        color:         C.mayoLight,
        letterSpacing: "0.14em",
        textTransform: "uppercase",
        opacity:       0.65,
      }}
    >
      MDT
    </div>
  </div>
);

// ── Conflict arrows ────────────────────────────────────────────────────────────
const ConflictArrow: React.FC<{ fromAngle: number; toAngle: number; opacity: number }> = ({
  fromAngle, toAngle, opacity,
}) => {
  const r = S.TABLE_RADIUS;
  const toRad = (d: number) => (d * Math.PI) / 180;
  // Convert to percentage of a 1000×1000 viewBox (table is centred at 500,500)
  const scale = 500 / r;
  const x1 = 500 + (r * 0.32) * Math.cos(toRad(fromAngle)) * scale / scale;
  const y1 = 500 + (r * 0.32) * Math.sin(toRad(fromAngle)) * scale / scale;
  const x2 = 500 + (r * 0.32) * Math.cos(toRad(toAngle)) * scale / scale;
  const y2 = 500 + (r * 0.32) * Math.sin(toRad(toAngle)) * scale / scale;

  return (
    <svg
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", opacity, pointerEvents: "none" }}
      viewBox="0 0 1000 1000"
    >
      <defs>
        <marker id="arr" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
          <path d="M0,0 L0,8 L8,4 z" fill={C.danger} />
        </marker>
      </defs>
      <line x1={x1} y1={y1} x2={x2} y2={y2}
        stroke={C.danger} strokeWidth="2" strokeDasharray="12 8" markerEnd="url(#arr)" />
    </svg>
  );
};

// ── Risk heatmap panel ─────────────────────────────────────────────────────────
const RiskHeatmap: React.FC<{ startFrame: number }> = ({ startFrame }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const containerOpacity = interpolate(frame, [startFrame, startFrame + 25], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <div
      style={{
        position: "absolute",
        right:    48,
        top:      "50%",
        transform: "translateY(-50%)",
        width:    S.RISK_PANEL_W,
        opacity:  containerOpacity,
        // Solid card so avatars + table don't bleed through
        background:    "rgba(15, 24, 34, 0.94)",
        border:        "1.5px solid rgba(255,255,255,0.10)",
        borderRadius:  18,
        padding:       "32px 36px",
        boxShadow:     "0 16px 56px rgba(0,0,0,0.75)",
        backdropFilter: "blur(6px)",
        zIndex:        50,
      }}
    >
      {/* Panel title */}
      <div
        style={{
          fontSize:      S.label,
          fontWeight:    800,
          fontFamily:    FONT,
          color:         C.mayoLight,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          marginBottom:  24,
          paddingBottom: 14,
          borderBottom:  "1px solid rgba(255,255,255,0.08)",
        }}
      >
        📊 Risk Assessment
      </div>
      {RISKS.map((risk, i) => {
        const rowProgress = spring({
          frame: frame - startFrame - i * 13,
          fps,
          config: { damping: 15, stiffness: 100 },
          durationInFrames: 22,
        });
        return (
          <div
            key={risk.label}
            style={{
              display:      "flex",
              alignItems:   "center",
              gap:          16,
              marginBottom: 14,
              transform:    `translateX(${interpolate(rowProgress, [0, 1], [30, 0])}px)`,
              opacity:      rowProgress,
            }}
          >
            <div style={{ flex: 1, fontSize: S.bodySmall, fontFamily: FONT, color: C.lightGrey, lineHeight: 1.3 }}>
              {risk.label}
            </div>
            <div
              style={{
                background:    `${risk.color}28`,
                border:        `1.5px solid ${risk.color}`,
                color:         risk.color,
                fontSize:      S.label,
                fontWeight:    700,
                fontFamily:    FONT,
                padding:       "5px 20px",
                borderRadius:  30,
                minWidth:      110,
                textAlign:     "center",
                letterSpacing: "0.05em",
                textTransform: "uppercase",
                flexShrink:    0,
              }}
            >
              {risk.level}
            </div>
          </div>
        );
      })}
    </div>
  );
};

// ── Final recommendation panel ────────────────────────────────────────────────
const FinalRecommendation: React.FC<{ startFrame: number }> = ({ startFrame }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const progress = spring({
    frame: frame - startFrame,
    fps,
    config: { damping: 12, stiffness: 80 },
    durationInFrames: 30,
  });

  return (
    <div
      style={{
        position:  "absolute",
        left:      48,
        top:       "50%",
        transform: `translateY(-50%) scale(${interpolate(progress, [0, 1], [0.92, 1])})`,
        width:     S.REC_PANEL_W,
        opacity:   interpolate(progress, [0, 1], [0, 1]),
        // Solid card — same treatment as Risk panel
        background:     "rgba(0, 18, 54, 0.95)",
        border:         "2px solid rgba(0,87,168,0.55)",
        borderRadius:   18,
        padding:        "32px 36px",
        boxShadow:      "0 16px 56px rgba(0,0,0,0.75)",
        backdropFilter: "blur(6px)",
        zIndex:         50,
      }}
    >
        <div
          style={{
            fontSize:      S.label,
            fontWeight:    700,
            fontFamily:    FONT,
            color:         C.mayoLight,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            marginBottom:  14,
            paddingBottom: 14,
            borderBottom:  "1px solid rgba(0,87,168,0.35)",
          }}
        >
          ✅ MDT Final Recommendation
        </div>
        <div style={{ fontSize: S.bodySmall, fontFamily: FONT, color: C.white, lineHeight: 1.7 }}>
          Emergency IR-guided thrombolysis within 4 hours.<br />
          Withhold DAPT 24–48 h with cardiology co-management.<br />
          CrCl measurement mandatory before any anticoagulant dosing.<br />
          OR on standby for damage-control laparotomy.
        </div>
    </div>
  );
};

// ── Systemic gap banner ────────────────────────────────────────────────────────
const GapBanner: React.FC<{ opacity: number }> = ({ opacity }) => (
  <div
    style={{
      position:   "absolute",
      bottom:     S.BAR_H + 40,
      left:       "50%",
      transform:  "translateX(-50%)",
      background: "rgba(192,57,43,0.2)",
      border:     "2px solid rgba(192,57,43,0.6)",
      borderRadius: 10,
      padding:    "14px 36px",
      textAlign:  "center",
      opacity,
    }}
  >
    <div style={{ fontSize: S.body * 0.75, fontWeight: 800, fontFamily: FONT, color: C.danger, letterSpacing: "0.06em" }}>
      ⚡ SYSTEMIC GAP IDENTIFIED
    </div>
    <div style={{ fontSize: S.label, fontFamily: FONT, color: C.lightGrey, marginTop: 6 }}>
      Cardiology vs Vascular Surgery · DAPT continuity vs Revascularisation urgency
    </div>
  </div>
);

// ── Main Roundtable ────────────────────────────────────────────────────────────
export const Roundtable: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const govStart     = GS;
  const isGovernance = frame >= govStart;

  // Conflict arrows: appear ~200 frames into clash phase (scaled from 150)
  const conflictOpacity = interpolate(frame, [CS + 200, CS + 233], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  // Systemic gap banner: ~224 frames into clash phase (scaled from 168)
  const gapOpacity = interpolate(frame, [CS + 224, CS + 240], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  // Verified seal: enters 80 frames into governance phase (scaled from 60)
  const sealProgress = spring({
    frame: frame - (govStart + 80),
    fps,
    config: { damping: 10, stiffness: 80 },
    durationInFrames: 30,
  });
  const sealRotation = interpolate(sealProgress, [0, 1], [-25, 0]);

  // "MDT Consensus" text: 120–144 frames into governance phase (scaled from 90–108)
  const consensusOpacity = interpolate(frame, [govStart + 120, govStart + 144], [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <AbsoluteFill>
      <CircularTable />

      {/* HOD avatars */}
      {ROUNDTABLE_CAST.map((spec, i) => {
        const hasConflict = frame >= CS + 200;
        const isSpeaking  = frame >= BUBBLE_FRAMES[i] && frame < BUBBLE_FRAMES[i] + 60;
        return (
          <HOD_Avatar
            key={spec.name}
            specialist={spec}
            angleDeg={AVATAR_ANGLES[i]}
            enterFrame={ENTER_FRAMES[i]}
            showBubble={isSpeaking}
            bubbleFrame={BUBBLE_FRAMES[i]}
            conflict={hasConflict && (i === 1 || i === 2)}
          />
        );
      })}

      {/* Conflict arrows: Vascular (60°) vs Cardiology (120°) */}
      <ConflictArrow fromAngle={60}  toAngle={120} opacity={conflictOpacity} />
      <ConflictArrow fromAngle={120} toAngle={60}  opacity={conflictOpacity} />

      {/* Systemic gap banner */}
      {frame < govStart && <GapBanner opacity={gapOpacity} />}

      {/* Governance panels */}
      {isGovernance && <RiskHeatmap    startFrame={govStart} />}
      {isGovernance && <FinalRecommendation startFrame={govStart + 27} />}

      {/* Verified seal — appears centre */}
      {isGovernance && (
        <div
          style={{
            position:  "absolute",
            top:       "50%",
            left:      "50%",
            transform: `translate(-50%, -50%) rotate(${sealRotation}deg)`,
            opacity:   interpolate(sealProgress, [0, 1], [0, 1]),
            zIndex:    20,
          }}
        >
          <VerifiedSeal size={S.SEAL_SIZE} />
        </div>
      )}

      {/* Consensus text */}
      {isGovernance && (
        <div
          style={{
            position:      "absolute",
            bottom:        S.BAR_H + 36,
            left:          "50%",
            transform:     "translateX(-50%)",
            fontSize:      S.subheadline * 0.75,
            fontWeight:    800,
            fontFamily:    FONT,
            color:         C.verified,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            opacity:       consensusOpacity,
            whiteSpace:    "nowrap",
          }}
        >
          MDT Consensus Reached
        </div>
      )}
    </AbsoluteFill>
  );
};
