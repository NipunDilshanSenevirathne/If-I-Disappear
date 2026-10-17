// Recording a voice note in the browser, with a live level meter.
// Before upload the recording is turned into 16 kHz mono WAV: a format the Gemini API
// documents for audio, and the resolution Gemini reads audio at anyway. If the browser
// can't decode its own recording, the original file is sent instead.

import { useCallback, useEffect, useRef, useState } from "react";

export type RecorderError = "unsupported" | "denied" | "failed";

export function useRecorder() {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [level, setLevel] = useState(0);
  const [error, setError] = useState<RecorderError | null>(null);
  // true when the recording stopped without anyone pressing stop (the microphone was
  // unplugged or switched off): what was recorded is kept, and the page can add it
  const [stoppedByItself, setStoppedByItself] = useState(false);
  const ended = useRef<Blob | null>(null);
  const rec = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const timer = useRef<number | undefined>(undefined);
  const raf = useRef<number>(0);
  const audio = useRef<AudioContext | null>(null);
  const resolveStop = useRef<((b: Blob | null) => void) | null>(null);
  const discard = useRef(false);

  const quiet = useCallback(() => {
    window.clearInterval(timer.current);
    cancelAnimationFrame(raf.current);
    void audio.current?.close().catch(() => undefined);
    audio.current = null;
    setLevel(0);
  }, []);

  const start = useCallback(async (): Promise<boolean> => {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("unsupported");
      return false;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    } catch {
      setError("denied");
      return false;
    }
    try {
      const type = ["audio/webm;codecs=opus", "audio/mp4", "audio/ogg;codecs=opus"].find((t) => MediaRecorder.isTypeSupported(t));
      const r = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
      chunks.current = [];
      discard.current = false;
      ended.current = null;
      setStoppedByItself(false);
      r.ondataavailable = (e) => {
        if (e.data.size) chunks.current.push(e.data);
      };
      r.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = discard.current ? null : new Blob(chunks.current, { type: (r.mimeType || "audio/webm").split(";")[0] });
        if (resolveStop.current) {
          resolveStop.current(blob);
          resolveStop.current = null;
        } else if (blob && blob.size) {
          ended.current = blob;
          quiet();
          setRecording(false);
          setStoppedByItself(true);
        }
      };
      try {
        const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        const ac = new AC();
        const analyser = ac.createAnalyser();
        analyser.fftSize = 512;
        ac.createMediaStreamSource(stream).connect(analyser);
        const buf = new Uint8Array(analyser.fftSize);
        const tick = () => {
          analyser.getByteTimeDomainData(buf);
          let sum = 0;
          for (let i = 0; i < buf.length; i++) {
            const x = (buf[i] - 128) / 128;
            sum += x * x;
          }
          setLevel(Math.min(1, Math.sqrt(sum / buf.length) * 4));
          raf.current = requestAnimationFrame(tick);
        };
        tick();
        audio.current = ac;
      } catch {
        /* the meter is optional */
      }
      r.start(250);
      rec.current = r;
      setSeconds(0);
      setRecording(true);
      timer.current = window.setInterval(() => setSeconds((s) => s + 1), 1000);
      return true;
    } catch {
      stream.getTracks().forEach((t) => t.stop());
      setError("failed");
      return false;
    }
  }, []);

  const finish = useCallback(
    (keep: boolean) =>
      new Promise<Blob | null>((resolve) => {
        quiet();
        setRecording(false);
        const r = rec.current;
        rec.current = null;
        if (!r || r.state === "inactive") {
          const kept = keep ? ended.current : null;
          ended.current = null;
          setStoppedByItself(false);
          return resolve(kept);
        }
        discard.current = !keep;
        resolveStop.current = resolve;
        r.stop();
      }),
    [quiet],
  );

  useEffect(
    () => () => {
      quiet();
      if (rec.current && rec.current.state !== "inactive") {
        discard.current = true;
        rec.current.stop();
      }
    },
    [quiet],
  );

  return { recording, seconds, level, error, stoppedByItself, start, stop: () => finish(true), cancel: () => finish(false) };
}

/** Decode a recording and re-encode it as 16 kHz mono 16-bit WAV. */
export async function toWav16k(blob: Blob): Promise<Blob> {
  const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  const ctx = new AC();
  try {
    const decoded = await ctx.decodeAudioData(await blob.arrayBuffer());
    const rate = 16_000;
    const length = Math.max(1, Math.ceil(decoded.duration * rate));
    const offline = new OfflineAudioContext(1, length, rate);
    const src = offline.createBufferSource();
    src.buffer = decoded;
    src.connect(offline.destination);
    src.start();
    const mono = (await offline.startRendering()).getChannelData(0);
    const out = new DataView(new ArrayBuffer(44 + mono.length * 2));
    const text = (at: number, s: string) => [...s].forEach((ch, i) => out.setUint8(at + i, ch.charCodeAt(0)));
    text(0, "RIFF");
    out.setUint32(4, 36 + mono.length * 2, true);
    text(8, "WAVE");
    text(12, "fmt ");
    out.setUint32(16, 16, true);
    out.setUint16(20, 1, true); // PCM
    out.setUint16(22, 1, true); // mono
    out.setUint32(24, rate, true);
    out.setUint32(28, rate * 2, true);
    out.setUint16(32, 2, true);
    out.setUint16(34, 16, true);
    text(36, "data");
    out.setUint32(40, mono.length * 2, true);
    for (let i = 0; i < mono.length; i++) {
      const v = Math.max(-1, Math.min(1, mono[i]));
      out.setInt16(44 + i * 2, v < 0 ? v * 0x8000 : v * 0x7fff, true);
    }
    return new Blob([out.buffer], { type: "audio/wav" });
  } finally {
    void ctx.close().catch(() => undefined);
  }
}

export function clock(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}
