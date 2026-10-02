# Runtime forensics
The deliverable is diagnosis, unless a fix was also requested.
1. Capture a live signal using the project's instrumentation: profile, heap, logs, or trace.
2. Reduce it to the hot path, retainer chain, or scheduling mechanism.
3. Test the mechanism with bounded instrumentation in an owned instance. Do not hot-patch a user's or production process without authorization.
4. Map the result to source and distinguish observation from hypothesis.
Return the signal, reduced finding, confirming evidence, locations, and gaps.
