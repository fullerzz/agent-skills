---
name: triage-pstack
description: "Triage upstream pstack changes against zstack with the Decisions CLI after a Hog update or when given cursor/plugins pull requests."
---

# Triage upstream pstack changes

Run from the zstack checkout that contains this skill and `scripts/triage_upstream.py`.

1. Verify the PRs in the update and pin each landed pstack change to its full merge SHA. Pin the zstack revision the user would port onto. Use the checkout's `HEAD` when the user leaves the target open, and report that choice. For a historical replay, use the pre-port zstack SHA. When the user asks to preview an open PR, pin its head SHA and treat the result as preliminary until it merges.
2. Inspect the pinned upstream patch and compare it with the pinned downstream code. Build one case per logical change, even when a single PR contains several changes. Capture the relevant public upstream diff or summary, matching public zstack code or shareable test observations, and any known platform requirements. State important unknowns in the evidence so the model can return `needs_context`.
3. Use a JSON encoder to save each case as one UTF-8 object in a scratch file. Supply `case_id`, the public `upstream_url` for the `cursor/plugins` PR, full 40-character `upstream_sha` and `downstream_sha` values, and `evidence` as text. Use distinct case IDs within a PR. The CLI sends the `evidence` string as case input.
4. Run the helper once per case with the checkout's `OPENAI_API_KEY` environment. If the command environment needs to load the approved `.envrc`, use the direnv form. Read the JSON output and keep the key out of case files, commands, and reports.

   ```sh
   uv run scripts/triage_upstream.py < "$case_file"
   ```

   ```sh
   direnv exec . uv run scripts/triage_upstream.py < "$case_file"
   ```

5. Report every case with its PR link, pinned SHAs, returned label, probabilities, and API confidence. Use `review` to prioritize deeper comparison, `needs_context` to identify a missing fact, `already_covered` to verify equivalent behavior, and `out_of_scope` to check the scope difference. Route errors or refusals to manual review and report any missing credentials once. Keep all cases visible during the pilot and end with the proposed follow-ups for the maintainer. Keep the triage pass read-only.
