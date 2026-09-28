// Short-lived, per-browser associations. These are approximate screen tracks, not identities.
export class PersonTracks {
  constructor() {
    this.reset();
  }

  reset() {
    this.tracks = [];
    this.nextId = 1;
  }

  update(items, width, height) {
    const persons = items.filter((item) => item.label === "person" && item.confidence >= 0.55);
    const used = new Set();
    for (const person of persons) {
      const center = [(person.box[0] + person.box[2]) / (2 * width), (person.box[1] + person.box[3]) / (2 * height)];
      let best = null;
      let distance = 0.22;
      for (const track of this.tracks) {
        if (used.has(track.id) || track.missed > 1) continue;
        const delta = Math.hypot(center[0] - track.center[0], center[1] - track.center[1]);
        if (delta < distance) { best = track; distance = delta; }
      }
      const area = (person.box[2] - person.box[0]) * (person.box[3] - person.box[1]) / (width * height);
      if (!best) {
        best = { id: this.nextId++, samples: [], missed: 0, announced: false, growthAnnounced: false };
        this.tracks.push(best);
      }
      best.center = center;
      best.item = person;
      best.missed = 0;
      best.samples.push(area);
      if (best.samples.length > 5) best.samples.shift();
      best.motion = viewSizeTrend(best.samples);
      used.add(best.id);
    }
    for (const track of this.tracks) {
      if (!used.has(track.id)) track.missed++;
    }
    const lost = this.tracks.filter((track) => track.missed >= 3).map((track) => track.id);
    this.tracks = this.tracks.filter((track) => track.missed < 3);
    return { visible: this.tracks.filter((track) => track.missed === 0), lost };
  }
}

// Screen size alone cannot distinguish a moving person from movement of the camera.
export function viewSizeTrend(samples) {
  if (samples.length < 4) return "establishing";
  const before = (samples[0] + samples[1]) / 2;
  const after = (samples.at(-1) + samples.at(-2)) / 2;
  if (before <= 0) return "establishing";
  if (after >= before * 1.25) return "larger in view";
  if (after <= before * 0.8) return "smaller in view";
  return "steady in view";
}
