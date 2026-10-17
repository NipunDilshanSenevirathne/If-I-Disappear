// Dates, plurals and small text helpers. English only, British-style dates ("Thu 12 Nov").

const LOCALE = "en-GB";

function at(iso: string): Date {
  return new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso);
}

export function fmtDay(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat(LOCALE, { weekday: "short", day: "numeric", month: "short" }).format(at(iso));
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "short", year: "numeric" }).format(at(iso));
}

export function fmtShort(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "short" }).format(at(iso));
}

export function fmtLong(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat(LOCALE, { weekday: "long", day: "numeric", month: "long" }).format(at(iso));
}

export function fmtMonth(iso: string): string {
  return new Intl.DateTimeFormat(LOCALE, { month: "long", year: "numeric" }).format(at(iso));
}

export function fmtTime(iso: string): string {
  return new Intl.DateTimeFormat(LOCALE, { hour: "numeric", minute: "2-digit" }).format(new Date(iso));
}

export function fmtAgo(iso: string, now = Date.now()): string {
  const s = Math.max(0, Math.round((now - Date.parse(iso)) / 1000));
  if (s < 45) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} h ago`;
  return fmtDate(iso);
}

export function daysBetween(a: string, b: string): number {
  return Math.round((Date.parse(`${b.slice(0, 10)}T00:00:00`) - Date.parse(`${a.slice(0, 10)}T00:00:00`)) / 86_400_000);
}

export function addDays(iso: string, n: number): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function cap(s: string): string {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}

export function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

export function minutes(n: number): string {
  if (n < 60) return `${n} min`;
  const h = Math.floor(n / 60);
  const m = n % 60;
  return m ? `${h} h ${m} min` : `${h} h`;
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("");
}

const AVATAR = ["#0f6c7a", "#6b4fb3", "#b2621a", "#13875a", "#2a5f9e", "#a5344f", "#5c6d12"];

export function avatarColor(id: string): string {
  let h = 0;
  for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return AVATAR[h % AVATAR.length];
}

export function pct(n: number, d: number): number {
  return d ? Math.round((100 * n) / d) : 0;
}
