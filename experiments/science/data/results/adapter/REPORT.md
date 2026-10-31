# Exact representation laws preserve information a known-field view loses

A small versioned TLV contract uses actual package-file metadata for mandatory name, size, offset and SHA-256 fields. Labelled synthetic fields add explicit/default name metadata and opaque optional future data. Unknown required fields fail closed; optional unknown fields survive without interpretation. This is an experimental contract, not a proposed universal AST or Protobuf repair.

Five blocks round-trip 512 records through a lossless JSON form, producing 2,560 byte-exact successes. Median complete batch roundtrip is 11.58 ms. The 512 binary records total 81,286 bytes; their JSON form is 161,623 bytes. Those sizes/costs describe the preserving representation, with no claim that it is the best encoding.

A lossy JSON view retains every projected known value yet changes 426 of 512 records because it discards presence/extension metadata. That candidate is rejected by the exact contract and supplies no valid performance win. The roundtrip boundary deliberately does not normalize the failed outputs, paralleling the prior Protobuf explicit/default counterexample.

Tests cover malformed/truncated/version geometry, duplicate tags, impossible native-width fields, required unknown extensions, and three distinct absent/default/explicit variants that share the same projected known values. Required semantics cannot be inferred from a convenient view alone. A second independent reader, broader schemas and actual production consumers remain future work.

[Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), [reproduce](../../README.md).
