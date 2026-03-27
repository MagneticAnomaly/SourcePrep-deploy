# Goalposts: Abstract Concept & Vision

## Overview
The **Goalposts** feature introduces a forward-looking, continuous planning pipeline to the application. Historically, this application has helped engineers work through technical bottlenecks. Goalposts extends this capability to the **product design and planning phase**, acting as an automated project manager and design partner.

Because AI enables developers to fluidly act as designers, copywriters, and project managers, we can leverage the existing epistemic knowledge of the codebase to automatically generate actionable plans. 

## The Core Concept
By first building the epistemology of the codebase, we can then perform a dedicated, intensive LLM analysis (a forward-looking reasoning step) to continuously build a plan and path forward. This LLM regularly audits the conceptual goals against the actual completeness of the codebase, and proactively proposes:
- New Sprints
- Research Phases
- Security Audits
- Architectural Plans

## Key Elements
1. **The Planning Pipeline:** Operates in the background when the app is idle (or on demand/queued first). It mimics the existing epistemic pipeline but is explicitly geared for planning and R&D.
2. **Dashboard "Goalposts" Panel:** A dedicated UI where the AI offers future sprints. The user can:
   - **Approve** to convert them into actionable tasks.
   - **Reject / Ignore** if they do not align with the product vision.
   - **Interrogate / Refine** (ask design questions to steer the AI's future proposals).
3. **Settings Integration:** Because the planning LLM call is large and potentially expensive/resource-intensive, this feature should be **off by default**. It can be enabled either in project settings or directly within the Goalposts panel.

## Unrealized Implications
Continuous background planning opens up significant design implications. The AI shifts from being a purely reactive assistant (solving bottlenecks) to a proactive partner (suggesting what to build next to achieve the product's ultimate vision).
>>> to resolve this We can simply add this as an additioan dashboard and CLI rcomponent/request and on the UI we can simply refresh/requst a new goalpoast LLM query/research/plan/etc
