// Non-visual feedback and first-run state. DOM-free so it can be tested in Node.

export const INTRO_KEY = "hecate.introSeen.v1";
export const VIBRATE_KEY = "hecate.vibrate";

// Distinct, short patterns: a warning should feel different from a notice.
export const VIBRATION_PATTERNS = {
  warn: [220, 90, 220],
  test: [120, 80, 120, 80, 120],
};

export const SOUND_CHECK_TEXT = "Hecate sound check. If you can hear this, alerts will reach you.";

/** Web Vibration is available in Android Chrome; iPhone browsers do not expose it. */
export function supportsVibration(nav = globalThis.navigator) {
  return Boolean(nav && typeof nav.vibrate === "function");
}

/** Vibrate for a kind of event if supported and enabled. Returns whether it vibrated. */
export function vibrateFor(kind, { enabled = true, nav = globalThis.navigator } = {}) {
  const pattern = VIBRATION_PATTERNS[kind];
  if (!enabled || !pattern || !supportsVibration(nav)) return false;
  try {
    return nav.vibrate(pattern) !== false;
  } catch {
    return false;
  }
}

// Storage can be missing or throw (private mode, blocked site data), so every access is guarded.
export function readFlag(storage, key, fallback) {
  try {
    const value = storage?.getItem(key);
    return value === null || value === undefined ? fallback : value === "1";
  } catch {
    return fallback;
  }
}

export function writeFlag(storage, key, value) {
  try {
    storage?.setItem(key, value ? "1" : "0");
  } catch {
    /* storage unavailable: the choice lasts for this visit only */
  }
}

/** Plain-language result of a sound check, for the More sheet. */
export function soundCheckMessage({ canSpeak, soundOn, vibrated }) {
  if (!canSpeak) return "This browser can't speak alerts. Try Chrome on Android or Safari on iPhone.";
  const buzz = vibrated ? " You should also have felt a buzz." : "";
  const off = soundOn ? "" : " Sound is off in the dock, so alerts won't be spoken until you turn it on.";
  return `Playing a sound check now. If you heard nothing, raise the media volume and check which device audio is going to.${buzz}${off}`;
}
