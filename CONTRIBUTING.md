# Contributing

1. Add or update a model profile under `src/orby4middleware/profiles/builtins/`.
2. Add captured-interface fixtures with all patient identifiers removed.
3. Add parser tests proving field boundaries, units, flags, duplicate handling and malformed frames.
4. Mark profiles `experimental`, `validated-lab`, or `vendor-documented` accurately.
5. Never claim an entire brand is compatible solely because one model has been tested.

Third-party protocol plugins can register entry points in the Python group `orby4middleware.protocols`.
