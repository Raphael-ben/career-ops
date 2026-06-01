# CV Fill Spec — Aviation Template (`cv-template-rb-aero.tex`)

## Source of truth

- **Aviation data**: `career-ops/config/profile_bank_aviation.json`
- **Professional experience & education**: `career-ops/config/profile_bank.json` (unchanged from main CV)

---

## Fill markers

| Marker | Source field | Format |
|--------|-------------|--------|
| `%%FILL:total_hours%%` | `aviation_qualifications.ppl_a.total_hours` | Number only — append " hrs total flight time" in template |

---

## Manually maintained fields

These fields are stable (change rarely) and are edited directly in the `.tex`. Always mirror changes back to `profile_bank_aviation.json`.

| Template location | Source field |
|---|---|
| Aircraft types bullet | `aviation_qualifications.ppl_a.aircraft_types` |
| Endorsements bullet | `aviation_qualifications.ppl_a.endorsements` |
| Night Rating date | `aviation_qualifications.ppl_a.ratings[0].date` |
| ICAO ELP date | `aviation_qualifications.ppl_a.ratings[1].date` |
| ATPL institution / URL | `atpl_training.school` / `atpl_training.school_url` |

---

## How to update flight hours

1. Update `profile_bank_aviation.json` → `aviation_qualifications.ppl_a.total_hours`
2. Replace `%%FILL:total_hours%%` in `cv-template-rb-aero.tex` with the new value
3. Recompile: `pdflatex -interaction=nonstopmode cv-template-rb-aero.tex`

---

## ATPL entry

When ATPL theoretical exams are completed or a module finishes, update:
- `atpl_training.status` in `profile_bank_aviation.json`
- The `\item` bullet text in the `experience` block for Astonfly in `cv-template-rb-aero.tex`
