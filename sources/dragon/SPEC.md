# Dragon Rise — SPEC (Aoi / Grok Bot)
Goal: ~7 s, 24 fps, 16:9 CG opener. Huge Eastern-style serpentine dragon bursts out of cracked ground under dawn mist, rises through cloud deck.
Tools: Blender 4.5.15 LTS (portable, headless) / Cycles CPU + OpenImageDenoise; numpy (procedural geometry); ffmpeg (grade, grain, audio mix); python synth audio.
Shots (one continuous camera move):
 0.0-1.4s  low camera in ground fog, dawn sun behind scene, mist drifting, ground bulges + glowing cracks, camera rumble.
 1.4-3.5s  ground bursts (plates, debris, mist shock-ring + swirl), head/horns emerge, jaw opens (roar).
 3.5-7.0s  body ascends (follow-the-leader on S path + travelling undulation), camera tilts/cranes, passes cloud deck, ends on silhouette vs bright clouds.  No title.
Dragon: procedural numpy mesh rebuilt per frame: tube body + ~27k overlapping scale tiles (true geometry -> rim-lit silhouettes), dorsal spines, lofted skull/jaw, teeth, horns, whiskers, glowing eyes.
Environment: polar-grid terrain w/ Voronoi crack plates, volumetric fog (noise, height falloff, swirl+shock ring around dragon), volumetric cloud deck, Nishita sky + sun low.
Camera: damped follow, handheld shake + eruption shake, DoF. Post (ffmpeg): grade, bloom, vignette, grain.
Budget: render <= ~90 min on 8 CPU cores, no GPU -> low spp + denoise; res/length scaled to measured speed (see report).
Audio: synthesized only (rumble, wind, crack impact, roar swell).
