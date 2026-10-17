// Spoken practice with the Gemini Live API, straight from the browser.
// The API key never reaches the browser: the server issues a single-use
// ephemeral token with the model and the practice partner's instructions locked in.

import { GoogleGenAI, Modality, type LiveServerMessage, type Session } from "@google/genai";

export type LiveState = "connecting" | "listening" | "speaking" | "ended" | "error";
export interface Turn {
  who: "me" | "partner";
  text: string;
}


function toBase64(bytes: Uint8Array): string {
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

function floatTo16(input: Float32Array): Int16Array {
  const out = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const v = Math.max(-1, Math.min(1, input[i]));
    out[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
  }
  return out;
}

/** Linear-interpolation resampler from the context's rate to 16 kHz (a pass-through at 16 kHz). */
function resampler(rate: number): (input: Float32Array) => Float32Array {
  if (rate === 16000) return (x) => x;
  const step = rate / 16000;
  let carry = new Float32Array(0);
  let t = 0;
  return (input) => {
    const data = new Float32Array(carry.length + input.length);
    data.set(carry);
    data.set(input, carry.length);
    const out: number[] = [];
    while (t + 1 < data.length) {
      const i = Math.floor(t);
      const f = t - i;
      out.push(data[i] * (1 - f) + data[i + 1] * f);
      t += step;
    }
    const keep = Math.floor(t);
    carry = data.slice(keep);
    t -= keep;
    return Float32Array.from(out);
  };
}

export interface LiveHandle {
  stop: () => Promise<{ me: string; partner: string; turns: Turn[] }>;
}

export async function startLive(opts: {
  token: string;
  model: string;
  apiVersion: string;
  onTurns: (turns: Turn[]) => void;
  onState: (s: LiveState) => void;
}): Promise<LiveHandle> {
  const turns: Turn[] = [];
  const push = (who: Turn["who"], text: string) => {
    if (!text) return;
    const last = turns[turns.length - 1];
    if (last && last.who === who) last.text += text;
    else turns.push({ who, text });
    opts.onTurns(turns.map((t) => ({ ...t })));
  };

  opts.onState("connecting");
  const mic = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
  // Gemini Live wants 16 kHz. Chrome can record straight into a 16 kHz context; browsers that
  // can't (Firefox) record at the device's rate and the samples are resampled below.
  let inCtx = new AudioContext({ sampleRate: 16000 });
  let src: MediaStreamAudioSourceNode;
  try {
    src = inCtx.createMediaStreamSource(mic);
  } catch {
    await inCtx.close();
    inCtx = new AudioContext();
    src = inCtx.createMediaStreamSource(mic);
  }
  const to16k = resampler(inCtx.sampleRate);
  const outCtx = new AudioContext({ sampleRate: 24000 });
  let playAt = 0;
  const playing = new Set<AudioBufferSourceNode>();

  const ai = new GoogleGenAI({ apiKey: opts.token, httpOptions: { apiVersion: opts.apiVersion } });
  let session: Session | null = null;
  let closed = false;

  const onMessage = (m: LiveServerMessage) => {
    const sc = m.serverContent;
    if (!sc) return;
    if (sc.interrupted) {
      playing.forEach((n) => n.stop());
      playing.clear();
      playAt = 0;
    }
    for (const part of sc.modelTurn?.parts ?? []) {
      const data = part.inlineData?.data;
      if (data && part.inlineData?.mimeType?.startsWith("audio/")) {
        opts.onState("speaking");
        const bytes = Uint8Array.from(atob(data), (c) => c.charCodeAt(0));
        const pcm = new Int16Array(bytes.buffer, bytes.byteOffset, Math.floor(bytes.byteLength / 2));
        const buf = outCtx.createBuffer(1, pcm.length, 24000);
        const ch = buf.getChannelData(0);
        for (let i = 0; i < pcm.length; i++) ch[i] = pcm[i] / 0x8000;
        const node = outCtx.createBufferSource();
        node.buffer = buf;
        node.connect(outCtx.destination);
        playAt = Math.max(playAt, outCtx.currentTime);
        node.start(playAt);
        playAt += buf.duration;
        playing.add(node);
        node.onended = () => {
          playing.delete(node);
          if (playing.size === 0 && !closed) opts.onState("listening");
        };
      }
    }
    if (sc.inputTranscription?.text) push("me", sc.inputTranscription.text);
    if (sc.outputTranscription?.text) push("partner", sc.outputTranscription.text);
  };

  session = await ai.live.connect({
    model: opts.model,
    config: { responseModalities: [Modality.AUDIO] },
    callbacks: {
      onopen: () => opts.onState("listening"),
      onmessage: onMessage,
      onerror: () => opts.onState("error"),
      onclose: () => {
        closed = true;
        opts.onState("ended");
      },
    },
  });

  // let the practice partner open the conversation
  session.sendClientContent({ turns: [{ role: "user", parts: [{ text: "Please start the practice now." }] }], turnComplete: true });

  // served from the app itself (public/pcm-capture.js): the CSP allows scripts from 'self' only
  await inCtx.audioWorklet.addModule("/pcm-capture.js");
  const worklet = new AudioWorkletNode(inCtx, "pcm-capture");
  let pending: Int16Array[] = [];
  let pendingLen = 0;
  worklet.port.onmessage = (e: MessageEvent<Float32Array>) => {
    if (closed || !session) return;
    const chunk = floatTo16(to16k(e.data));
    pending.push(chunk);
    pendingLen += chunk.length;
    if (pendingLen >= 1600) {
      const all = new Int16Array(pendingLen);
      let o = 0;
      for (const p of pending) {
        all.set(p, o);
        o += p.length;
      }
      pending = [];
      pendingLen = 0;
      session.sendRealtimeInput({ audio: { data: toBase64(new Uint8Array(all.buffer)), mimeType: "audio/pcm;rate=16000" } });
    }
  };
  src.connect(worklet);

  return {
    stop: async () => {
      closed = true;
      try {
        session?.sendRealtimeInput({ audioStreamEnd: true });
      } catch {
        /* already closed */
      }
      session?.close();
      mic.getTracks().forEach((tr) => tr.stop());
      worklet.disconnect();
      src.disconnect();
      await inCtx.close();
      playing.forEach((n) => n.stop());
      await outCtx.close();
      opts.onState("ended");
      return {
        me: turns.filter((t) => t.who === "me").map((t) => t.text.trim()).join("\n"),
        partner: turns.filter((t) => t.who === "partner").map((t) => t.text.trim()).join("\n"),
        turns,
      };
    },
  };
}
