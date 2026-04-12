import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { C, FONT, S, PILLARS, Pillar } from "./constants";

const PillarCard: React.FC<{ pillar: Pillar; enterFrame: number }> = ({
  pillar,
  enterFrame,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const progress = spring({
    frame: frame - enterFrame,
    fps,
    config: { damping: 14, stiffness: 90 },
    durationInFrames: 28,
  });

  return (
    <div
      style={{
        width:        S.PILLAR_W,
        background:   pillar.bg,
        border:       `2px solid ${pillar.color}`,
        borderRadius: 18,
        padding:      "40px 44px",
        opacity:      interpolate(progress, [0, 1], [0, 1]),
        transform:    `translateY(${interpolate(progress, [0, 1], [50, 0])}px)`,
        boxShadow:    `0 16px 48px ${pillar.color}44`,
        position:     "relative",
        overflow:     "hidden",
      }}
    >
      {/* Top accent bar */}
      <div
        style={{
          position:     "absolute",
          top:          0,
          left:         0,
          right:        0,
          height:       7,
          background:   pillar.color,
          borderRadius: "18px 18px 0 0",
        }}
      />

      {/* Icon + labels */}
      <div style={{ display: "flex", alignItems: "center", gap: 18, marginBottom: 22 }}>
        <span style={{ fontSize: 56 }}>{pillar.icon}</span>
        <div>
          <div
            style={{
              fontSize:      S.body,
              fontWeight:    800,
              fontFamily:    FONT,
              color:         C.white,
              letterSpacing: "-0.01em",
              lineHeight:    1.2,
            }}
          >
            {pillar.label}
          </div>
          <div
            style={{
              fontSize:   S.label,
              fontFamily: FONT,
              color:      pillar.color,
              fontWeight: 700,
              marginTop:  6,
            }}
          >
            Pillar {pillar.id}
          </div>
        </div>
      </div>

      {/* Query */}
      <div
        style={{
          fontSize:     S.label,
          fontFamily:   FONT,
          color:        C.lightGrey,
          fontStyle:    "italic",
          marginBottom: 22,
          lineHeight:   1.5,
        }}
      >
        {pillar.sublabel}
      </div>

      {/* Tier + count */}
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <span
          style={{
            background:    `${pillar.color}33`,
            border:        `1.5px solid ${pillar.color}`,
            color:         C.white,
            fontSize:      S.label,
            fontWeight:    700,
            fontFamily:    FONT,
            padding:       "5px 18px",
            borderRadius:  30,
            letterSpacing: "0.03em",
          }}
        >
          {pillar.tier}
        </span>
        <span
          style={{
            background: "rgba(255,255,255,0.08)",
            color:      C.lightGrey,
            fontSize:   S.label,
            fontFamily: FONT,
            padding:    "5px 18px",
            borderRadius: 30,
          }}
        >
          {pillar.articles} article{pillar.articles !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Evidence gap note */}
      {pillar.hasGap && (
        <div
          style={{
            marginTop:    20,
            background:   "rgba(200,116,0,0.18)",
            border:       "1.5px dashed #C87400",
            borderRadius: 8,
            padding:      "12px 16px",
            fontSize:     S.micro,
            fontFamily:   FONT,
            color:        "#FFB347",
            lineHeight:   1.6,
          }}
        >
          ⚠️ No RCT evidence for this intersection. Management relies on Tier 2 Guidelines + MDT Consensus.
        </div>
      )}
    </div>
  );
};

export const EvidenceMatrix: React.FC<{ startFrame: number }> = ({ startFrame }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const headerProgress = spring({
    frame: frame - startFrame,
    fps,
    config: { damping: 14, stiffness: 90 },
    durationInFrames: 25,
  });

  const badgeProgress = spring({
    frame: frame - startFrame - 10,
    fps,
    config: { damping: 10, stiffness: 120 },
    durationInFrames: 22,
  });

  return (
    <AbsoluteFill
      style={{
        display:        "flex",
        flexDirection:  "column",
        alignItems:     "center",
        justifyContent: "center",
        paddingBottom:  S.BAR_H,
        gap:            40,
      }}
    >
      {/* Header */}
      <div
        style={{
          textAlign: "center",
          opacity:   interpolate(headerProgress, [0, 1], [0, 1]),
          transform: `translateY(${interpolate(headerProgress, [0, 1], [20, 0])}px)`,
        }}
      >
        <div
          style={{
            fontSize:      S.headline,
            fontWeight:    800,
            fontFamily:    FONT,
            color:         C.white,
            letterSpacing: "-0.02em",
            marginBottom:  10,
          }}
        >
          Evidence Matrix
        </div>
        <div style={{ fontSize: S.subheadline * 0.7, fontFamily: FONT, color: C.lightGrey }}>
          Multi-Pillar PubMed Decomposition
        </div>
      </div>

      {/* Pillar cards */}
      <div style={{ display: "flex", gap: 36, alignItems: "flex-start" }}>
        {PILLARS.map((pillar, i) => (
          <PillarCard
            key={pillar.id}
            pillar={pillar}
            enterFrame={startFrame + 18 + i * 22}
          />
        ))}
      </div>

      {/* PubMed Verified badge */}
      <div
        style={{
          display:     "flex",
          alignItems:  "center",
          gap:         14,
          background:  "rgba(30,132,73,0.15)",
          border:      "2px solid rgba(30,132,73,0.5)",
          borderRadius: 40,
          padding:     "14px 32px",
          transform:   `scale(${badgeProgress})`,
          opacity:     badgeProgress,
        }}
      >
        <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
          <circle cx="14" cy="14" r="12" stroke="#1E8449" strokeWidth="2" />
          <polyline points="8,14 12,18 20,10" stroke="#1E8449" strokeWidth="2.5"
            strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span
          style={{
            fontSize:      S.body * 0.75,
            fontWeight:    700,
            fontFamily:    FONT,
            color:         "#1E8449",
            letterSpacing: "0.06em",
            textTransform: "uppercase",
          }}
        >
          PubMed Verified Evidence
        </span>
      </div>
    </AbsoluteFill>
  );
};
