# Trace forensics
1. Identify the supplied artifact format and use an existing parser.
2. Query samples/frames/retainers directly; convert to a queryable form only if necessary.
3. Narrow the hot path or retention mechanism and map symbols to source.
4. Compare a paired capture where available. Without corroboration, label the strongest supported hypothesis.
Return a cited diagnosis and artifact paths. No fix or new production capture unless requested.
