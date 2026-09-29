# Memory subsystem

`providers.py` separates the private per-user Hindsight bank from PostgreSQL application data. `DemoMemoryProvider` makes the product usable without credentials. `privacy.py` redacts email addresses and Indian phone numbers before retention and returns only safe redaction events for logs.

The shared source-trust bank lives in PostgreSQL because it is aggregate product data, not private user memory. Never use a user's private memory bank as a source-trust bank.
