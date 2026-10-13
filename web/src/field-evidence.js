const EXPORT_VERSION = "hecate-field-evidence/v1";

function safeObservation(observation) {
  return {
    label: observation.label,
    confidence: observation.confidence,
    position: observation.position,
    clock: observation.clock,
  };
}

/**
 * Keeps a privacy-preserving record of a field-test session in browser memory.
 * It deliberately records model outputs and latency, never camera frames.
 */
export function createFieldEvidenceLog({ now = () => new Date() } = {}) {
  const entries = [];

  function recordAnalysis({ mode, result }) {
    const observations = (result.observations || []).map(safeObservation);
    const entry = {
      timestamp: now().toISOString(),
      mode,
      image: { width: result.width, height: result.height },
      inference_ms: result.inference_ms,
      observation_count: observations.length,
      observations,
    };
    entries.push(entry);
    return entry;
  }

  function exportPayload() {
    return {
      format: EXPORT_VERSION,
      exported_at: now().toISOString(),
      privacy: "No image frames or audio are included. This file contains only model outputs and timing metadata.",
      session: entries.map((entry) => ({ ...entry, observations: [...entry.observations] })),
    };
  }

  return {
    get count() { return entries.length; },
    recordAnalysis,
    exportPayload,
    clear() { entries.length = 0; },
  };
}
