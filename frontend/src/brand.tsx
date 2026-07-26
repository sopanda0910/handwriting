// Inkwell brand mark. A drop of ink settling into a well: the year's work,
// collected. Colors: ink navy, mint drop, paper cream.

export function LogoMark({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-hidden>
      <rect x="1" y="1" width="46" height="46" rx="13" fill="var(--ink-deep, #1e2a5a)" />
      <path
        d="M24 7.5c2.9 3.5 4.8 6 4.8 8.3a4.8 4.8 0 1 1-9.6 0c0-2.3 1.9-4.8 4.8-8.3z"
        fill="#7fd1c0"
      />
      <path
        d="M17 22h14v3.2c2.3 1.4 3.7 3.6 3.7 6.2 0 4.8-4.1 7.8-10.7 7.8s-10.7-3-10.7-7.8c0-2.6 1.4-4.8 3.7-6.2V22z"
        fill="#f6f2e8"
      />
      <rect x="15.2" y="19" width="17.6" height="3.2" rx="1.6" fill="#f6f2e8" />
    </svg>
  );
}

export function Wordmark({ compact = false }: { compact?: boolean }) {
  return (
    <span className="wordmark-row">
      <LogoMark size={compact ? 30 : 40} />
      <span className="wordmark">
        Inkwell
        {!compact && <em className="tagline">the story of a school year</em>}
      </span>
    </span>
  );
}
