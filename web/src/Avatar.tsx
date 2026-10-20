import { LogoMark } from "./Logo";

export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  const letters = words.length === 1 ? [words[0]] : [words[0], words[words.length - 1]];
  return letters.map((w) => [...w][0].toUpperCase()).join("");
}

export function Avatar({ name, tone }: { name: string; tone: "ai" | "tutor" | "student" }) {
  return (
    <span className={`avatar avatar-${tone}`} aria-hidden="true">
      {tone === "ai" ? <LogoMark /> : initials(name)}
    </span>
  );
}
