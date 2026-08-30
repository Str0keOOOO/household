# Delivery record

## Current state

Repository scaffolding is complete and BEHAVIOR-1K v3.7.2 is registered as an
unmodified, shallow Git submodule at commit
`88454bd04f75dc57c00ab1f1a00bcde1ff505950`. Installation and demo execution are
intentionally pending the user's explicit acceptance of the required licenses.

## Local changes made

- Created the top-level Git repository, its local-only identity, ignore rules,
  version lock, repository policy, and source/resource documentation.
- Added setup, preflight, Miniforge bootstrap, installation, version-capture, and
  two upstream-demo launch scripts under `scripts/`.
- Added no patches or commits inside third-party source code.

## Resources downloaded so far

- BEHAVIOR-1K source submodule: v3.7.2, commit
  `88454bd04f75dc57c00ab1f1a00bcde1ff505950`, complete.
- Miniforge: v26.5.3-0, SHA-256 verified as
  `14db468222ad564658656f769506056209b6dc375f5e7dfd31eb5ebbf08fa529`, installed
  only at `.tools/miniforge3`.
- No Conda environment, Isaac Sim package, Hugging Face asset, decryption key, or
  R1Pro asset bundle has been downloaded yet.

## Remaining work

1. Verify the submodule commit and commit the repository scaffold.
2. Obtain explicit confirmation of the Conda terms, NVIDIA EULA, and BEHAVIOR
   dataset license.
3. Bootstrap local Miniforge, run the minimal supported install, and capture exact
   resolved versions.
4. Run the official quickstart and the bundled R1Pro BEHAVIOR demo, then update
   this record with commands, logs, outcomes, and any upstream source changes
   (expected: none).
