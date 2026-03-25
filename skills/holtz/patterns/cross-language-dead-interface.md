---
name: cross-language-dead-interface
version: "1.0.0"
discovered: 2026-03-25
languages: []
categories: [bug/logic, design/maintenance]
---

# Cross-Language Dead Interface

## Description

Fields, uniforms, bindings, or parameters written in one language and intended to be consumed in another (host code to shader, application to SQL/template, frontend to backend DTO) where the receiving side never reads them — or vice versa. The sending side computes and transmits data every cycle; the receiving side ignores it. A feature silently stops working, or compute is wasted indefinitely.

Distinct from `dead-code-latent-path` (unreachable code behind toggles within one language) and `dual-parser-divergence` (two parsers for the same format). This pattern spans a language boundary where the compiler cannot see both sides.

The root cause is that cross-language interfaces are invisible to each language's toolchain. The host compiler cannot see that a shader no longer reads a uniform field. The shader compiler cannot see that the host stopped writing one. Renaming, removing, or refactoring on either side produces no error, warning, or test failure.

## Detection Heuristic

### Grep-based scan

```bash
# Find struct/class fields used in cross-language data transfer
grep -rnP '(Uniforms|Params|Constants|Bindings)\b' --include='*.swift' --include='*.cpp' --include='*.rs' --include='*.py' .
```

```bash
# Find host-side data transfer calls
grep -rnP '(setBytes|setBuffer|glUniform|bind|uniform\s+\w+)' .
```

```bash
# Find SQL parameter binding
grep -rnP '(\?|:\w+|%s|%\(\w+\))' --include='*.py' --include='*.js' --include='*.go' . | grep -iP '(execute|query|prepare)'
```

### Manual triage

1. For each cross-language data struct: list every field
2. For each field: does the sending side write it? Does the receiving side read it?
3. Are field names consistent across the boundary? (Typos won't produce compiler errors)
4. Were any fields added or removed on one side without updating the other?

### LLM-based structured check

> "Identify all data structures that cross a language boundary (host→shader, app→SQL, code→template). For each field in the sending struct: is it read on the receiving side? For each field read on the receiving side: is it written on the sending side? Flag orphaned fields in either direction."

## Indicators

- Struct fields computed every frame/request but never referenced in the corresponding shader/query/template
- Shader/query reads a field the host side never populates (undefined data consumed silently)
- Rename on one side not propagated to the other (no compiler error across the boundary)
- Performance cost: unnecessary computation and data transfer every cycle
- Features that "stopped working" after a refactor on one side of the boundary

## Example

### Before (buggy)

```python
# host.py — Python sending uniforms to a GLSL shader
class ParticleUniforms:
    def __init__(self):
        self.time = 0.0
        self.particle_count = 100
        self.smooth_blend_radius = 0.5  # Added for a blur feature
        self.smoothed_iterations = 4    # Added for a blur feature

    def upload(self, shader):
        shader.set_uniform("time", self.time)
        shader.set_uniform("particleCount", self.particle_count)
        shader.set_uniform("smoothBlendRadius", self.smooth_blend_radius)  # Uploaded every frame
        shader.set_uniform("smoothedIterations", self.smoothed_iterations)  # Uploaded every frame

# particle.glsl — the shader was refactored, blur feature removed
# uniform float time;
# uniform int particleCount;
# // smoothBlendRadius and smoothedIterations were removed from shader
# // but host still computes and uploads them every frame — no error
```

### After (fixed)

```python
# host.py — removed dead fields
class ParticleUniforms:
    def __init__(self):
        self.time = 0.0
        self.particle_count = 100

    def upload(self, shader):
        shader.set_uniform("time", self.time)
        shader.set_uniform("particleCount", self.particle_count)
```

## Related Patterns

- [dead-code-latent-path](dead-code-latent-path.md) — single-language dead code behind toggles
- [doc-spec-drift](doc-spec-drift.md) — the interface contract drifted without anyone noticing
- [dual-parser-divergence](dual-parser-divergence.md) — two sides interpreting shared data differently
