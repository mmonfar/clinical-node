import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { C, FONT, S, Specialist } from "./constants";
import { MedicalIcon, SurgicalIcon, SupportIcon } from "./Icons";

interface HOD_AvatarProps {
  specialist:  Specialist;
  angleDeg:    number;
  enterFrame:  number;
  showBubble:  boolean;
  bubbleFrame: number;
  conflict?:   boolean;
}

export const HOD_Avatar: React.FC<HOD_AvatarProps> = ({
  specialist,
  angleDeg,
  enterFrame,
  showBubble,
  bubbleFrame,
  conflict = false,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const entryProgress = spring({
    frame: frame - enterFrame,
    fps,
    config: { damping: 12, stiffness: 100 },
    durationInFrames: 30,
  });

  const bubbleOpacity = interpolate(
    frame,
    [bubbleFrame, bubbleFrame + 18],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const pulse = conflict ? 1 + 0.05 * Math.sin((frame * Math.PI) / 8) : 1;

  const angleRad = (angleDeg * Math.PI) / 180;
  const cx = S.TABLE_RADIUS * Math.cos(angleRad);
  const cy = S.TABLE_RADIUS * Math.sin(angleRad);

  const Icon =
    specialist.category === "Surgical" ? SurgicalIcon
    : specialist.category === "Medical" ? MedicalIcon
    : SupportIcon;

  const catColor = {
    Surgical: C.surgical,
    Medical:  C.medical,
    Support:  C.support,
  }[specialist.category];

  // Bubble appears on the side pointing toward the centre
  const bubbleOnRight = cx < 0;

  return (
    <div
      style={{
        position:   "absolute",
        left:       "50%",
        top:        "50%",
        transform:  `translate(calc(-50% + ${cx}px), calc(-50% + ${cy}px))
                     scale(${entryProgress * pulse})`,
        display:    "flex",
        flexDirection: "column",
        alignItems: "center",
        gap:        12,
        opacity:    entryProgress,
        // Elevate the currently speaking avatar above all siblings.
        // Each avatar root has a CSS transform which creates a stacking
        // context — without an explicit z-index the DOM render order wins,
        // causing later avatars to occlude earlier ones' speech bubbles.
        zIndex:     showBubble ? 200 : 1,
      }}
    >
      {/* Avatar circle */}
      <div
        style={{
          width:        S.AVATAR_D,
          height:       S.AVATAR_D,
          borderRadius: "50%",
          background:   `radial-gradient(circle at 35% 35%, ${catColor}cc, ${catColor})`,
          border:       `4px solid ${conflict ? C.danger : catColor}`,
          boxShadow:    conflict
            ? `0 0 28px ${C.danger}99`
            : `0 0 20px ${catColor}66`,
          display:        "flex",
          alignItems:     "center",
          justifyContent: "center",
        }}
      >
        <Icon size={S.AVATAR_ICON} color={C.white} />
      </div>

      {/* Name */}
      <div
        style={{
          fontSize:   S.bodySmall,
          fontWeight: 700,
          fontFamily: FONT,
          color:      C.white,
          textAlign:  "center",
          maxWidth:   200,
          lineHeight: 1.25,
          textShadow: "0 2px 6px rgba(0,0,0,0.9)",
        }}
      >
        {specialist.name}
      </div>

      {/* Priority chip */}
      <div
        style={{
          fontSize:     S.label,
          fontFamily:   FONT,
          color:        catColor,
          background:   `${catColor}22`,
          border:       `1.5px solid ${catColor}55`,
          borderRadius: 30,
          padding:      "5px 16px",
          fontWeight:   600,
          textAlign:    "center",
          maxWidth:     220,
          lineHeight:   1.3,
        }}
      >
        {specialist.priority}
      </div>

      {/* Speech bubble */}
      {showBubble && (
        <div
          style={{
            position:     "absolute",
            [bubbleOnRight ? "left" : "right"]: S.AVATAR_D / 2 + 20,
            top:          0,
            width:        S.SPEECH_W,
            background:   C.white,
            borderRadius: 14,
            padding:      "18px 22px",
            fontSize:     S.caption,
            fontFamily:   FONT,
            color:        "#1A2332",
            lineHeight:   1.55,
            opacity:      bubbleOpacity,
            boxShadow:    "0 8px 32px rgba(0,0,0,0.40)",
            zIndex:       10,
            borderLeft:   bubbleOnRight ? `4px solid ${catColor}` : "none",
            borderRight:  bubbleOnRight ? "none" : `4px solid ${catColor}`,
          }}
        >
          <div
            style={{
              fontSize:      S.micro,
              fontWeight:    700,
              color:         catColor,
              marginBottom:  8,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
            }}
          >
            {specialist.name}
          </div>
          {specialist.statement}
        </div>
      )}
    </div>
  );
};
