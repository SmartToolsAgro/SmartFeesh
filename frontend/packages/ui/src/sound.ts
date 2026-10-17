// The tone of a new notification (D-175): two short notes made by the browser, so no sound file is downloaded.
// Browsers only let a page make sound after the person touched it once: `unlockSound` waits for that first touch.

const SOUND_KEY = "frutti-sound";

let context: AudioContext | null = null;

function audio(): AudioContext | null {
  if (context) return context;
  try {
    context = new AudioContext();
  } catch {
    return null; // no Web Audio (old browser, tests)
  }
  return context;
}

/** Whether the tone is on for this device; on unless the person turned it off. */
export function isSoundOn(): boolean {
  try {
    return localStorage.getItem(SOUND_KEY) !== "off";
  } catch {
    return true;
  }
}

export function setSoundOn(on: boolean): void {
  try {
    localStorage.setItem(SOUND_KEY, on ? "on" : "off");
  } catch {
    // Not kept: the tone is on again on the next visit.
  }
}

/** Let the page make sound from the person's first touch or key press on. Returns the way to stop waiting. */
export function unlockSound(): () => void {
  const stop = () => {
    window.removeEventListener("pointerdown", unlock);
    window.removeEventListener("keydown", unlock);
  };
  const unlock = () => {
    void audio()?.resume();
    stop();
  };
  window.addEventListener("pointerdown", unlock);
  window.addEventListener("keydown", unlock);
  return stop;
}

/** Play the notification tone, unless it is turned off; a phone also vibrates briefly. */
export function playChime(): void {
  if (!isSoundOn()) return;
  if ("vibrate" in navigator) navigator.vibrate(180);
  const ctx = audio();
  if (!ctx) return;
  if (ctx.state === "suspended") void ctx.resume();
  const start = ctx.currentTime + 0.02;
  for (const [frequency, delay] of [
    [880, 0],
    [1318.5, 0.15],
  ] as const) {
    const oscillator = ctx.createOscillator();
    const gain = ctx.createGain();
    oscillator.type = "sine";
    oscillator.frequency.value = frequency;
    gain.gain.setValueAtTime(0.0001, start + delay);
    gain.gain.exponentialRampToValueAtTime(0.3, start + delay + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + delay + 0.45);
    oscillator.connect(gain).connect(ctx.destination);
    oscillator.start(start + delay);
    oscillator.stop(start + delay + 0.5);
  }
}
