# PLAXIS 3D support

The embankment template uses a cross-section in X/Z, extruded along Y into a soil volume. Supply `embankment_length` in metres explicitly alongside the existing height, top width, clay thickness and slope ratios. The 2D tutorial does not establish this longitudinal dimension. Missing length is rejected before execution.

Input defaults to localhost:10000 and Output to localhost:10001, consistently for script generation and direct execution. Run the intended application/server; these ports alone do not identify which PLAXIS version is listening. Settlement is read from Uz for 3D (Uy for 2D); horizontal 3D displacement combines Ux and Uy at matching nodes.

Initial clay uses Drained material. Fill is inactive initially, activated in separate Drained/Undrained construction phases, followed by a Safety phase for each branch. The Undrained assignment resolves current staged soil clusters by initial material.

The other templates (slope, foundation, retaining wall, excavation) currently have only 2D geometry and are explicitly rejected for 3D rather than silently generating 2D commands. They require separate 3D geometry and loading specifications.

Validation: automated script/parameter/result-axis tests pass. No installed PLAXIS 3D is available in the cloud environment. The user's 3D PDF manual was not available here and the attempted external manual download returned HTTP 403. Generated geometry and API compatibility still require validation on the target PLAXIS release before relying on numerical results.
