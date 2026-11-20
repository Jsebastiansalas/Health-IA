/** Placa en blanco: decoración de estados vacíos (una película sin estudio). */
export function PlacaVacia({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 160 200" className={className} fill="none" aria-hidden>
      <rect x="6" y="14" width="148" height="180" rx="4" fill="#1b2430" stroke="#e4f3f8" strokeOpacity="0.25" />
      <path d="M122 14v22a2 2 0 0 0 2 2h30" stroke="#e4f3f8" strokeOpacity="0.2" />
      <g fill="#cfe3ea">
        <rect x="22" y="52" width="70" height="6" rx="3" opacity="0.35" />
        <rect x="22" y="74" width="116" height="4" rx="2" opacity="0.2" />
        <rect x="22" y="86" width="104" height="4" rx="2" opacity="0.2" />
        <rect x="22" y="98" width="112" height="4" rx="2" opacity="0.2" />
      </g>
      <path d="M26 142c22-26 56-26 78-4s30 6 36-6" stroke="#ffc247" strokeOpacity="0.85" strokeWidth="3" strokeLinecap="round" strokeDasharray="1 9" />
      <rect x="50" y="2" width="22" height="16" rx="3" fill="#56636f" />
      <rect x="92" y="2" width="22" height="16" rx="3" fill="#56636f" />
    </svg>
  );
}
