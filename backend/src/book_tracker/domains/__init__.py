"""One package per domain.

A domain's registry entry, field spec, vocabularies, identity strategy, URL recognizer,
provider adapter and importers live together under `domains/<item_type>/`, so the team
adding one edits one directory (technical spec 6.6). What a domain *is* lives in
`domain/spec.py`; which domains exist lives in `domain/registry.py`.
"""
