// Audio worklet for spoken practice: hands each block of microphone samples to the page,
// which converts them to 16 kHz PCM for Gemini Live. A file of its own (not a blob: URL)
// so the Content-Security-Policy can keep script-src to 'self'.
class PcmCapture extends AudioWorkletProcessor {
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch) this.port.postMessage(ch.slice(0));
    return true;
  }
}
registerProcessor("pcm-capture", PcmCapture);
