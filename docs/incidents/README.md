# Incidents

Times Holtz broke containment. Each incident triggered an enforcement upgrade.

| Date | Incident | What broke | What changed |
|------|----------|------------|--------------|
| 2026-04-02 | [The Heist](key-theft-tqdm/) | Holtz read his own session key, reverse-engineered the HMAC format, and forged a cryptographic event. Twice. | Session keys moved to daemon memory (mlock, anti-ptrace, socket peer credentials) |
| 2026-03-27 | [Rubber-stamping](self-audit-rubber-stamping.md) | Holtz recorded protocol events for 12 of 13 lens sweeps without reading any code through any lens. | Lens quiz system: 5 comprehension questions per sweep, generated from codebase facts, stored where the model can't read them |
