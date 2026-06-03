Hey Luca,

ctx looks like exactly the kind of environment where review volume becomes a real infrastructure problem, not just a UX annoyance.

Here's how codewise handles it today and where it falls short for your use case:

What works now:

- fail_on: high + min_severity means agents and CI only surface what matters — you're not triaging noise
- The GitHub Action runs per-PR automatically, so each agent worktree gets its own isolated review — no cross-contamination
- Regex rules fire with zero LLM calls, so they're fast enough to run synchronously as a pre-commit or pre-push gate even with parallel agents
- --format json output is machine-readable — you can aggregate or filter findings across agent runs programmatically
- The MCP server (review_code tool) lets the agent call a review inline before it commits — it can self-correct before the findings ever reach you

What's missing that ctx would need:

- No concept of an agent session or run ID — all findings are file/line scoped. You'd have no native way to group "these 12 findings came from agent run #4 in worktree X"
- No aggregated view across concurrent runs — you'd have to build that on top of the JSON output
- No deduplication if two agents touch overlapping files — you'd get duplicate findings
- The MCP server is per-repo, not multi-tenant by design

I'm curious how ctx surfaces review results today — does it have a unified review pane per agent, or is it more of a pass/fail gate at the worktree level? That would shape what integration makes most sense.

The gap I'd consider building: a --run-id flag and a lightweight findings aggregation layer. With the existing JSON output it's doable without touching the core engine — ctx could tag each agent run and get a consolidated view across worktrees.

Happy to dig into this further if it's useful.

Naveen
