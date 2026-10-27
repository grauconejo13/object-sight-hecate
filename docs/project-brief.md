# Project Brief

## Problem

People often move through environments while their attention is divided: navigating an unfamiliar city, jogging, hiking, walking at night, dealing with poor visibility, or focusing on a task directly ahead.

Object-Sight Hecate explores whether computer vision can act as **artificial peripheral awareness** by monitoring surrounding motion and spatial change and selectively bringing important observations to the user's attention.

## Product Behavior

The user deliberately starts an awareness session before a walk, jog, hike, or similar activity.

The system observes the environment and remains quiet unless an event crosses an alert threshold.

Candidate directional language uses the user's body as the reference frame:

```text
12 = ahead
3  = right
6  = behind
9  = left
```

Example:

> Cyclist approaching, 5 o'clock.

## Intended Progression

```text
object detection
      ↓
tracking
      ↓
spatial relationships
      ↓
movement over time
      ↓
relevance / risk conditions
      ↓
selective alert or follow-up action
```

The central question is not merely "what objects are visible?"

It is:

> What changed around the user that they may need to know about?

## Hecate Concept

Hecate is the working name for a future multi-camera architecture. A possible physical system may use three wide-angle camera views to increase peripheral coverage around the wearer.

For the competition prototype, ordinary webcams, recorded video, phone cameras, or simulated multi-view feeds are sufficient. Hardware should only be introduced if it meaningfully improves the demonstration.

## Candidate Use Cases

- City night walking
- Cautious travel in an unfamiliar area
- Jogging and running
- Hiking and trail awareness
- Low-visibility conditions
- Accessibility assistance
- Later: mobility and worksite awareness

## Privacy and Safety Boundaries

Object-Sight should describe **observable behavior and geometry**, not motives or identity.

Appropriate:

- `Person approaching from rear-left.`
- `Vehicle remained nearby through two direction changes.`
- `Obstacle blocks the path ahead.`

Not appropriate:

- `That person is dangerous.`
- `That person is lying.`
- `That person looks suspicious.`

The project should not rely on facial identification or attempt to infer criminality, trustworthiness, personality, or emotion from appearance.

## Hackathon Focus

The competition build should prove a narrow end-to-end experience rather than an oversized feature list. Likely priorities are:

1. Reliable OpenCV 5 perception.
2. Tracking and temporal state.
3. User-relative spatial awareness.
4. Selective alerts based on meaningful change.
5. A substantive NVIDIA Nemotron component on Nebius Token Factory that summarises structured visual evidence for the wearer, without sitting on the time-critical alert path.
6. Evaluation, failure cases, and limitations.
