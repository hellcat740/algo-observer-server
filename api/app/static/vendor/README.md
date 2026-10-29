# Local Three.js runtime

The observation space vendors its runtime assets so `/space` does not depend on a CDN at runtime.

- Package: `three@0.170.0`
- `three.module.min.js`: https://unpkg.com/three@0.170.0/build/three.module.min.js
- `OrbitControls.js`: https://unpkg.com/three@0.170.0/examples/jsm/controls/OrbitControls.js
- License: MIT (Three.js project)

`space.html` maps the bare `three` import used by OrbitControls to the local module through an import map. Update both files together when changing the Three.js version.
