import React from "react";

interface IconProps {
  size?: number;
  color?: string;
}

/** Scalpel + Shield — Surgical specialties */
export const SurgicalIcon: React.FC<IconProps> = ({ size = 40, color = "#FFFFFF" }) => (
  <svg width={size} height={size} viewBox="0 0 40 40" fill="none">
    <path
      d="M20 3 L34 9 L34 21 C34 29 27 35 20 37 C13 35 6 29 6 21 L6 9 Z"
      fill={color}
      fillOpacity={0.15}
      stroke={color}
      strokeWidth={1.5}
    />
    <line x1="13" y1="27" x2="27" y2="13" stroke={color} strokeWidth={2} strokeLinecap="round" />
    <line x1="23" y1="11" x2="29" y2="17" stroke={color} strokeWidth={1.5} strokeLinecap="round" />
    <circle cx="12" cy="28" r="2.5" fill={color} />
    <line x1="16" y1="24" x2="28" y2="20" stroke={color} strokeWidth={1} strokeOpacity={0.6} strokeLinecap="round" />
  </svg>
);

/** Stethoscope + Pulse — Medical specialties */
export const MedicalIcon: React.FC<IconProps> = ({ size = 40, color = "#FFFFFF" }) => (
  <svg width={size} height={size} viewBox="0 0 40 40" fill="none">
    {/* ECG line */}
    <polyline
      points="4,24 9,24 12,18 15,30 18,20 21,24 36,24"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      fill="none"
    />
    {/* Stethoscope head */}
    <circle cx="20" cy="32" r="4" stroke={color} strokeWidth={1.5} fill="none" />
    <circle cx="20" cy="32" r="1.5" fill={color} />
    {/* Tube */}
    <path d="M12 10 Q12 6 16 6 Q20 6 20 10 L20 28" stroke={color} strokeWidth={1.5} fill="none" strokeLinecap="round" />
    <path d="M28 10 Q28 6 24 6 Q20 6 20 10" stroke={color} strokeWidth={1.5} fill="none" strokeLinecap="round" />
    <circle cx="12" cy="11" r="2" fill={color} />
    <circle cx="28" cy="11" r="2" fill={color} />
  </svg>
);

/** Cross + Monitor — Support / Critical Care specialties */
export const SupportIcon: React.FC<IconProps> = ({ size = 40, color = "#FFFFFF" }) => (
  <svg width={size} height={size} viewBox="0 0 40 40" fill="none">
    {/* Monitor */}
    <rect x="4" y="8" width="32" height="22" rx="2" stroke={color} strokeWidth={1.5} fill="none" />
    <line x1="16" y1="30" x2="24" y2="30" stroke={color} strokeWidth={1.5} />
    <line x1="16" y1="30" x2="14" y2="34" stroke={color} strokeWidth={1.5} strokeLinecap="round" />
    <line x1="24" y1="30" x2="26" y2="34" stroke={color} strokeWidth={1.5} strokeLinecap="round" />
    {/* Cross */}
    <rect x="17" y="12" width="6" height="14" rx="1" fill={color} fillOpacity={0.9} />
    <rect x="13" y="16" width="14" height="6" rx="1" fill={color} fillOpacity={0.9} />
  </svg>
);

/** PubMed microscope icon */
export const MicroscopeIcon: React.FC<IconProps> = ({ size = 80, color = "#FFFFFF" }) => (
  <svg width={size} height={size} viewBox="0 0 80 80" fill="none">
    {/* Eyepiece */}
    <rect x="34" y="4" width="12" height="8" rx="2" fill={color} />
    {/* Body tube */}
    <rect x="36" y="12" width="8" height="20" rx="1" fill={color} />
    {/* Nosepiece */}
    <rect x="30" y="32" width="20" height="6" rx="1" fill={color} />
    {/* Objective lens */}
    <rect x="37" y="38" width="6" height="12" rx="3" fill={color} fillOpacity={0.9} />
    {/* Stage */}
    <rect x="20" y="50" width="40" height="5" rx="2" fill={color} />
    {/* Base arm */}
    <rect x="22" y="55" width="6" height="16" rx="1" fill={color} />
    {/* Base */}
    <rect x="16" y="68" width="48" height="8" rx="3" fill={color} />
    {/* Light beam */}
    <line x1="40" y1="50" x2="40" y2="62" stroke={color} strokeWidth={1} strokeDasharray="2 2" strokeOpacity={0.5} />
    {/* PubMed badge dot */}
    <circle cx="62" cy="14" r="10" fill="#E74C3C" />
    <text x="62" y="18" textAnchor="middle" fill="#FFFFFF" fontSize="8" fontWeight="bold" fontFamily="Arial">PM</text>
  </svg>
);

/** Verified stamp seal */
export const VerifiedSeal: React.FC<IconProps & { label?: string }> = ({
  size = 120,
  color = "#1E8449",
  label = "MDT VERIFIED",
}) => (
  <svg width={size} height={size} viewBox="0 0 120 120" fill="none">
    {/* Solid dark backing — prevents canvas bleed-through */}
    <circle cx="60" cy="60" r="50" fill="rgba(10,20,32,0.94)" />
    {/* Outer gear spokes */}
    {Array.from({ length: 12 }).map((_, i) => {
      const angle = (i * 30 * Math.PI) / 180;
      const x1 = 60 + 52 * Math.cos(angle);
      const y1 = 60 + 52 * Math.sin(angle);
      const x2 = 60 + 58 * Math.cos(angle);
      const y2 = 60 + 58 * Math.sin(angle);
      return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth={4} strokeLinecap="round" />;
    })}
    <circle cx="60" cy="60" r="48" stroke={color} strokeWidth={2.5} fill="none" />
    {/* Inner filled ring — opaque green background for checkmark */}
    <circle cx="60" cy="60" r="40" fill={color} fillOpacity={0.22} stroke={color} strokeWidth={1.5} />
    {/* Checkmark */}
    <polyline
      points="38,60 53,75 82,44"
      stroke={color}
      strokeWidth={7}
      strokeLinecap="round"
      strokeLinejoin="round"
      fill="none"
    />
    {/* Label */}
    <text x="60" y="98" textAnchor="middle" fill={color} fontSize="9" fontWeight="800"
      fontFamily="'Inter', 'Helvetica Neue', sans-serif" letterSpacing="1.5">
      {label}
    </text>
  </svg>
);
