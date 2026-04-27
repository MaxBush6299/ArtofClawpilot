---
name: "backward-compatible-contract-evolution"
description: "How to evolve persisted data contracts while preserving legacy records without migration"
domain: "data-contracts"
confidence: "high"
source: "earned"
tools:
  - name: "git"
    description: "Extracts legacy data from git history for manual restoration"
    when: "Recovering overwritten data after contract changes"
---

## Context

Use this pattern when evolving persisted JSON contracts (like `data/gallery.json`) where:
- New fields or validation rules are added
- Legacy records exist in git history without the new fields
- Records must coexist across schema versions
- Migration scripts add complexity without behavioral benefit

This pattern applies to append-only ledgers, versioned APIs, and any persisted state where historical records must remain valid under new validation rules.

## Patterns

### Fallback Methods for Missing Fields

When adding a new required field, provide a fallback method that computes it from existing fields:

```python
@dataclass
class GalleryImageRecord:
    id: str
    run_id: str | None = None  # New field, optional for legacy records
    
    def effective_run_id(self) -> str:
        return self.run_id or self.id
```

**Key principles:**
- New fields are optional in the dataclass
- Fallback methods use deterministic logic (not random or time-based)
- Validation uses the fallback method, not the raw field
- Legacy records remain valid without schema migration

### Validation Against Effective Values

Update validation logic to check computed effective values, not raw fields.

**Key principles:**
- Validation enforces uniqueness/constraints on effective values
- Legacy records with missing fields pass validation via fallback
- New records with explicit fields behave identically

### Optional Serialization

When writing records back to JSON, only emit fields that are explicitly set.

**Key principles:**
- Legacy records round-trip without gaining new fields
- New records explicitly write new fields
- JSON shape varies by record age (acceptable for append-only ledgers)

### Manual Restoration from Git History

When legacy records are overwritten during contract evolution, restore via git extraction to preserve exact original metadata.

## Examples

See `orchestrator/contracts.py`: `GalleryImageRecord.effective_run_id()`
See `orchestrator/validation.py`: `validate_gallery_state()` (line 102-104)

## Anti-Patterns

- Do not require migration scripts for optional fields with deterministic fallbacks
- Do not backfill missing fields if fallback methods provide correct behavior
- Do not validate raw optional fields directly
- Do not re-run execution logic to restore overwritten records if git history preserves exact original metadata

## References

- Issue #16: Multi-run idempotency refactor
- Commit afb67f9: Manual restoration of legacy gallery image