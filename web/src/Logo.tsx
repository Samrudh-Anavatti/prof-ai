export function Logo() {
  return (
    <span className="logo">
      <svg className="logo-mark" viewBox="0 0 32 32" aria-hidden="true">
        <rect width="32" height="32" rx="8" />
        <path d="M6 13 16 8l10 5-10 5z" className="logo-cap" />
        <path d="M10 16v5c0 1.5 3 3 6 3s6-1.5 6-3v-5" className="logo-band" />
      </svg>
      <span className="logo-word">
        Prof<span className="logo-ai">AI</span>
      </span>
    </span>
  );
}
