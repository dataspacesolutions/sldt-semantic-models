# Chem-X DMP — vendored pending official publication

Source package: `OneDrive_2026-09-09 - DMP v0.8.1.zip`, dated 2026-09-04,
marked "provided for internal feedback purposes only".

Chem-X has no public model repository yet. These artefacts are carried here so
the catalogue can serve the DMP during the Chem-X MVP (project ends 30 Nov 2026).

Both files carry deliberate corrections. **Do not "fix" either back toward the
published package** — see `my_docs/DMP MVP/SCHEMA_VALIDATION_FINDINGS.md` in
cx_ai_agents for the full report, which has been sent to Chem-X.

## `Dmp-schema.json` — 12 hoisted nodes

Chem-X's `models/v08/dmp.dereferenced.schema.json` with **12 misplaced
`additionalProperties` nodes hoisted** out of their `properties` block (defect
class B). The dereferenced variant is used because this repository's convention
is one self-contained schema per aspect; `$ref`s to sibling files would not
resolve once the file is served from blob storage.

As shipped, those twelve declare a *property named* `additionalProperties` whose
schema is the boolean `false`, which both inverts the intended contract (the
objects accept any extra property) and crashes schema walkers. Everything else
is verbatim, including the `$id`, which therefore still reads
`.../dmp.dereferenced.schema.json`. The model's canonical identity is
`https://chem-x.de/models/v08/dmp.schema.json`, and that is the value recorded
as `nativeId` on the catalogue row.

**Measured, and the gate for any new version:** exactly 12 nodes hoist, and the
schema flattens to **741** fields through the versioning service's own
flattener. The count is 741 *before and after* the hoist, with identical column
sets — the correction fixes the contract without moving a single reporting
column. If a new package hoists a different number of nodes, or moves the field
count, re-run the defect report before vendoring it.

## `Dmp.json` — 10 corrected enum defects

Chem-X's `examples/dmp-v08-example.json` with **ten enum defects corrected**
(defect class A). Their shipped examples fail their own schema with 10 errors;
publishing one unchanged as the template would teach every consumer the wrong
values.

Seven are casing or codification slips with a correct member available:

| Path | Package ships | Template uses |
|---|---|---|
| `/nameplate/granularity` | `batch` | `Batch` |
| `/components/0/granularity` | `batch` | `Batch` |
| `/components/0/type` | `material` | `Unpacked` |
| `…/pcfStatus` | `active` | `ACT` |
| `…/pcfPartialFull` | `partial` | `cradle-to-gate` |
| `…/pcfCharacterizationFactors` | `IPCC AR6` | `AR6` |
| `…/pcfGeography/regionOrSubregion` | `Western Europe` | `155` |

Two are **required fields whose enum has no member for the case at hand**, so
they cannot be omitted — the schema lists both in `required`, which means a
conformant document has to name a member even when none describes the truth.
The nearest valid member is used:

| Path | Package ships | Template uses | Why |
|---|---|---|---|
| `…/massBalancingCalculationApproach` | `not-applicable` | `Conventional reference` | Enum is `Conventional reference \| Conventional reference & Inventory \| Inventory`. The sibling `massBalancingUsed` is `false`, so no mass-balance approach applies at all — but the field is required. |
| `…/pcfProductOrSectorSpecificRules` | free text | `["TfS_V3"]` | Closed enum, and required. TfS Guideline V3.0 is the chemical-industry PCR, so it is the honest pick for a chemical DMP. |

**This is worth escalating to Chem-X as a contradiction, not a typo:** a
required field over a closed enum with no applicable member makes a conformant
document impossible to write for that case. Either the enums need a
`not-applicable` member, or the fields must stop being required.

One is omitted, because it is optional and the enum genuinely lacks the value:

| Path | Package ships | Template | Why |
|---|---|---|---|
| `…/mixture/supplementalHazardClassification` | `["EUH204"]` | omitted | `EUH204` ("Contains isocyanates…") is missing from `CHX-E0010` — and it is the phrase the isocyanate example they shipped actually needs. |

## Validation gates

Run all three on every new Chem-X version before merging it:

```bash
# 1. exactly 12 nodes hoist out of `properties`
# 2. the schema flattens to 741 fields through the service's flattener
# 3. the template validates against the schema with ZERO errors
python -c "
import json, jsonschema
schema = json.load(open('io.chemx.dmp/0.8.1/gen/Dmp-schema.json', encoding='utf-8'))
template = json.load(open('io.chemx.dmp/0.8.1/gen/Dmp.json', encoding='utf-8'))
errors = list(jsonschema.Draft202012Validator(schema).iter_errors(template))
print('OK' if not errors else f'{len(errors)} ERRORS - do not merge')
"
```

Gate 3 is the load-bearing one: this repository must not carry a template that
fails its own schema.

## File naming

The template is `gen/Dmp.json`, **not** `gen/Dmp-template.json`. The versioning
service builds the template path as `{namespace}/{version}/gen/{Aspect}.json`
and only uses the `-template.json` suffix for the *blob* it writes. Every other
aspect in this repository follows the same convention (`Pcf.json`,
`Circularity.json`).

## Never amend a version in place

The versioning service skips a blob that already exists, so editing
`io.chemx.dmp/0.8.1/gen/Dmp-schema.json` here does **nothing** once 0.8.1 has
been ingested: blob storage keeps the old bytes and nothing warns you. The
catalogue then serves content that no longer matches this repository.

This bites Chem-X harder than Catena-X, which cuts a new version directory per
change. Chem-X's 0.8.1 is explicitly an *"internal feedback"* package and they
are collecting corrections right now — including the twelve we reported — so
reissuing 0.8.1 under the same number is a realistic thing for them to do.

**Every Chem-X change gets a new version directory, even a correction.** If
Chem-X reissues 0.8.1 in place, publish it here as **0.8.2** and record the
divergence in this file.

## When Chem-X fixes these upstream

Revert our patches in the same commit that takes their corrected package. The
three gates above will tell you whether a new package still needs them.

## Adding a new version

Costs no code. Commit
`io.chemx.dmp/<version>/{metadata.json, gen/Dmp-schema.json, gen/Dmp.json}`;
the next cron tick's tree walk finds the new `metadata.json` and ingests it,
because the namespace is registered `UPSTREAM`. 0.8.1 stays active alongside
it — retire it by setting its `metadata.json` lifecycle to anything other than
`release`, which maps to DEPRECATED.

## Removing this directory

When Chem-X publishes officially, delete this whole directory and set
`source_repo="chemx-official"` on the `io.chemx.dmp` row in
`cx_semantic_aspect_models_versioning_service`'s `namespace_registry.py` —
**after** filling in that repository's real coordinates and setting
`confirmed=True`, which the service enforces. Do it in the wrong order and the
run aborts rather than silently retiring the rows.
Nothing else changes — the URNs, blob paths and Mongo rows are identical either
way. The full procedure is in that repo's `doc/chemx-switchover.md`.
