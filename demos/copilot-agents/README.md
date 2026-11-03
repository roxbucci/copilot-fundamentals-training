# Copilot Agents Demo

Use the following 3 files to setup your Copilot Agents demo. 
Paste the ISSUE.md file into a new issue in that repository. 

## What this demo shows
- Assign an issue to Copilot to start an agent task
- Monitor progress in AgentHQ
- Re-steer mid-session with a new requirement
- Review the resulting PR like a teammate’s work

## Demo files
- `ISSUE.md` contains the exact issue text to copy/paste into GitHub
- `STEER.md` contains the mid-session requirement change to paste while the agent is working

## Quick demo steps
1. Create a new GitHub Issue by copying the Title and Body from `ISSUE.md`
2. Assign the issue to Copilot to start the agent task
3. Open AgentHQ to monitor progress
4. Paste `STEER.md` into the agent session to re-steer the work
5. Review the PR diff for clarity, completeness, and constraints.
6. Verify the PR edited the README.md file by adding priority levels plus the steered examples. 

---

## Ticket Triage Policy (Current)

Assess ticket severity, then use the default priority mapping below.

### Severity levels
- Low means minor annoyance with an easy workaround
- Medium means a meaningful user impact but workarounds exist
- High means blocks key workflows or causes data loss

### Current rules
- Triage happens daily
- Address P0 incidents first, then work by priority

### Priority levels
- **P0 — Immediate:** Active widespread outage, security incident, or ongoing data loss; respond now.
- **P1 — Urgent:** Blocks a key workflow or causes serious impact; address next.
- **P2 — Normal:** Meaningful impact, but a workaround exists; schedule soon.
- **P3 — Low:** Minor annoyance with an easy workaround; handle when capacity allows.

### Default Severity → Priority
- High → P1
- Medium → P2
- Low → P3
- Escalate to P0 when immediate response is needed, regardless of the default.

### How to triage in 60 seconds
1. Confirm who is affected and which workflow is impacted.
2. Check severity, scope, and available workarounds.
3. Set the default priority from the mapping; use P0 only for immediate-response incidents.
4. Record the impact, priority rationale, and next action.
