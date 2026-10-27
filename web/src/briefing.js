// "Ask Hecate": optional Nemotron scene briefing. DOM-free helpers for testing.

/** Build the request for the phone camera from the latest analysed detections. */
export function phoneBriefingRequest(items) {
  return {
    source: "phone",
    observations: (items || []).slice(0, 50).map((item) => ({
      label: item.label,
      confidence: item.confidence,
      clock: item.clock,
      position: item.position,
      ...(item.motion ? { motion: item.motion } : {}),
    })),
  };
}

/** Short provenance line shown under the briefing, so judges and users see who wrote it. */
export function briefingTag(result) {
  if (!result) return "";
  if (result.provider === "nemotron") {
    const timing = result.cached ? "cached" : result.latency_ms != null ? `${(result.latency_ms / 1000).toFixed(1)} s` : "";
    return ["NVIDIA Nemotron on Nebius", timing].filter(Boolean).join(" · ");
  }
  switch (result.nebius) {
    case "unavailable": return "Nebius unavailable · local summary";
    case "guarded": return "Nemotron reply withheld by safety check · local summary";
    case "skipped": return "Camera offline · local summary";
    default: return "Nebius error · local summary";
  }
}

export function askButtonLabel(status) {
  if (!status) return "Ask Hecate for a scene briefing";
  return status.available
    ? "Ask Hecate for a scene briefing (Nemotron on Nebius)"
    : "Ask Hecate for a scene briefing (Nebius unavailable, local summary)";
}
