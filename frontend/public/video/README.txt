12-KOUL local cinematic atmosphere

The supplied Higgsfield kitchen clip is integrated as the shared background.
It plays directly and stays mounted across category switches.

Shared default and fallback: 12koul-kitchen.mp4
Optional future category overrides (register supplied files in atmosphereVideos):
  12koul-salad-atmosphere.mp4
  12koul-sandwich-atmosphere.mp4
  12koul-plats-atmosphere.mp4
  12koul-drinks-atmosphere.mp4

Mapping: src/experience/Atmosphere.tsx. Overrides are empty by default to avoid
requesting nonexistent category clips. A failed registered category video falls back to
the kitchen loop. Missing kitchen video leaves the animated lighting environment.
Video is decorative, muted, inline, and looped. Inactive videos pause. Reduced
motion and background tabs suspend playback. No video is used as the meal model.

Suggested delivery: H.264 MP4, 1080p, 24 fps, 8-12 seconds, no audio, under 8 MB.
Match first/last frames for a true seamless loop (the browser cannot fix a cut).
Keep contrast restrained; the frontend applies depth, warmth and legibility masks.

Kitchen brief for future production:
The two official 12-KOUL characters preparing food in their professional kitchen;
warm tungsten light, restrained steam, natural ingredient movement, slow camera,
macro food detail, no dialogue, no text, no UI, no exaggerated acting.
Use the actual character references when producing the footage.
