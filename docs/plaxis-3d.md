# PLAXIS 3D support

`plaxis_commands` now provides structured calls to the running Input or Output Remote Scripting API, independently of these fixed templates. The model can inspect `commands`/`info`, build a new problem in batches, and read phase/output evidence. Parameters support literal JSON values and object references, including aliases within one batch. No Python or shell evaluation is used. The tool connects to the current project and never starts a new project implicitly. Each failed batch reports completed steps and whether the failing command started; do not replay completed mutations.

This is a general execution mechanism, not a validated implementation of the Excavation in sand tutorial. Read the actual manual, retain its problem type and data, and verify the API on the installed release. Do not replace an unsupported template with an embankment or silently omit anchors/struts/loading. Preview results may be truncated; `summarize` computes numeric extrema over the entire result array within a batch. A successful batch alone does not establish convergence or correctness.

The embankment template uses a cross-section in X/Z, extruded along Y into a soil volume. Supply `embankment_length` in metres explicitly alongside the existing height, top width, clay thickness and slope ratios. The 2D tutorial does not establish this longitudinal dimension. Missing length is rejected before execution.

Input defaults to localhost:10000 and Output to localhost:10001, consistently for script generation and direct execution. Run the intended application/server; these ports alone do not identify which PLAXIS version is listening. Settlement is read from Uz for 3D (Uy for 2D); horizontal 3D displacement combines Ux and Uy at matching nodes.

Initial clay uses Drained material. Fill is inactive initially, activated in separate Drained/Undrained construction phases, followed by a Safety phase for each branch. The Undrained assignment resolves current staged soil clusters by initial material.

The other templates (slope, foundation, retaining wall, excavation) currently have only 2D geometry and are explicitly rejected for 3D rather than silently generating 2D commands. They require separate 3D geometry and loading specifications.

Validation: automated script/parameter/result-axis tests pass. No installed PLAXIS 3D is available in the cloud environment. The user's 3D PDF manual was not available here and the attempted external manual download returned HTTP 403. Generated geometry and API compatibility still require validation on the target PLAXIS release before relying on numerical results.
