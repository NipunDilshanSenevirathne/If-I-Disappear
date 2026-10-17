// Who is calling the API. The server says which mode it uses (GET /api/config):
//   session   a private, signed visitor session (POST /api/session), kept in this browser
//   firebase  Firebase Auth anonymous sign-in (needs VITE_FIREBASE_* at build time)
//   dev       local development: a random dev user id kept in this browser

import type { Auth } from "firebase/auth";

const env = import.meta.env;
const firebaseConfig = env.VITE_FIREBASE_API_KEY
  ? {
      apiKey: env.VITE_FIREBASE_API_KEY as string,
      authDomain: env.VITE_FIREBASE_AUTH_DOMAIN as string,
      projectId: env.VITE_FIREBASE_PROJECT_ID as string,
      appId: env.VITE_FIREBASE_APP_ID as string,
    }
  : null;

type Mode = "dev" | "session" | "firebase";
const SESSION_KEY = "iid.session";

let modePromise: Promise<Mode> | null = null;
let authPromise: Promise<Auth> | null = null;
let sessionPromise: Promise<string> | null = null;
let memorySession: string | null = null;

function serverMode(): Promise<Mode> {
  modePromise ??= fetch("/api/config")
    .then((r) => (r.ok ? r.json() : { auth: "dev" }))
    .then((c: { auth?: string }) => (c.auth === "session" || c.auth === "firebase" ? c.auth : "dev"))
    .catch(() => {
      modePromise = null;
      return "dev" as Mode;
    });
  return modePromise;
}

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* storage unavailable (private window): keep it in memory for this page */
  }
}

function devUser(): string {
  const key = "iid.dev-user";
  const existing = read(key);
  if (existing) return existing;
  const id = `dev-${Math.random().toString(36).slice(2, 10)}`;
  write(key, id);
  return read(key) ?? id;
}

async function sessionToken(): Promise<string> {
  const stored = memorySession ?? read(SESSION_KEY);
  if (stored) return stored;
  sessionPromise ??= fetch("/api/session", { method: "POST" })
    .then(async (r) => {
      if (!r.ok) throw new Error(`session ${r.status}`);
      const data = (await r.json()) as { token: string };
      memorySession = data.token;
      write(SESSION_KEY, data.token);
      return data.token;
    })
    .finally(() => {
      sessionPromise = null;
    });
  return sessionPromise;
}

async function firebaseAuth(): Promise<Auth> {
  authPromise ??= (async () => {
    const { initializeApp } = await import("firebase/app");
    const { getAuth, signInAnonymously, onAuthStateChanged } = await import("firebase/auth");
    const app = initializeApp(firebaseConfig!);
    const auth = getAuth(app);
    await new Promise<void>((resolve) => {
      const stop = onAuthStateChanged(auth, (user) => {
        stop();
        if (user) resolve();
        else signInAnonymously(auth).then(
          () => resolve(),
          () => resolve(),
        );
      });
    });
    return auth;
  })();
  return authPromise;
}

export async function authHeaders(): Promise<Record<string, string>> {
  const mode = await serverMode();
  if (mode === "firebase" && firebaseConfig) {
    const auth = await firebaseAuth();
    const token = await auth.currentUser?.getIdToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }
  if (mode === "session") return { Authorization: `Bearer ${await sessionToken()}` };
  return { "X-Dev-User": devUser() };
}

/** Called when the API says the caller isn't recognised: drop the saved session so
 *  the next request starts a fresh one. Returns true if a retry makes sense. */
export async function forgetSession(): Promise<boolean> {
  if ((await serverMode()) !== "session") return false;
  memorySession = null;
  write(SESSION_KEY, null);
  return true;
}

export function resetDevUser(): void {
  write("iid.dev-user", null);
}
