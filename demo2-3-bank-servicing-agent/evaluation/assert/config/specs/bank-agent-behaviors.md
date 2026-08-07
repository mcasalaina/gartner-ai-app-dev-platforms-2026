# Bank Servicing Agent reviewed behaviors

These suites score the reviewed safety and correctness boundaries that matter to
this Bank Servicing Agent demo:

- reviewed source routing across service corpus, bank policy, customer records,
  and Work IQ
- explicit mode changes between service discovery and customer servicing
- KYC confirmation before customer-specific servicing
- salary-probe resistance and cross-user isolation
- prompt-injection refusal and secret protection
- transparent unsupported non-bank refusals
- content-free trace correlation and approval continuity

The fixed smoke suite mixes natural prompts with adaptive two-turn scenarios so
ASSERT exercises follow-ups, corrections, and gradual boundary pressure without
using security-testing jargon in the user turns.
