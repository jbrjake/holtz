---
name: Use project's own skills directly
description: When user says to apply a skill from the project (like "use skills/holtz/"), read and follow the skill file directly rather than invoking a superpowers skill with a similar name.
type: feedback
---

When user says to use a skill from the project directory (e.g., "use skills/holtz/"), read the SKILL.md file directly and follow its protocol. Do not invoke a different superpowers skill (like bug-hunter) that has overlapping trigger words.

**Why:** User corrected when the superpowers bug-hunter skill was invoked instead of the project's own holtz skill. The project's own skill is the one being developed/tested and the user wants it applied to itself (dogfooding).

**How to apply:** When the user references a path to a skill directory in the project, always read and follow that specific skill file rather than matching on keywords to find a superpowers skill.
