"""Strict FHIR R4 scalar Observation import, not a FHIR server or general validator."""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any

from ..dates import instant, local_day
from ..errors import InputError
from ..models import CycleDataset, Measurement, Provenance
from ..serialization import loads, parse_model, read_text

# Codes describe distinct quantities; no coding here means 'period began'.
DEFAULT_CODES = {
    ("http://loinc.org", "8867-4"): "heart_rate",
    ("http://loinc.org", "8310-5"): "body_temperature",
}


class FHIRObservationAdapter:
    """Map explicit patient references to local pseudonyms; unknown patients are errors.

    imported_at is when this system obtained the export, not its effective time.
    FHIR versionId is opaque and is never coerced to a ledger revision.
    A changed Observation needs an explicit revision_map when merging exports.
    """

    def __init__(self, *, subject_map: Mapping[str, str], imported_at: str,
                 utc_offset_minutes: int,
                 code_map: Mapping[tuple[str, str], str] | None = None,
                 revision_map: Mapping[str, int] | None = None,
                 source_id: str = "fhir-r4",
                 body_site_map: Mapping[tuple[str, str], str] | None = None,
                 method_map: Mapping[tuple[str, str], str] | None = None) -> None:
        if not isinstance(subject_map, Mapping):
            raise InputError("invalid_subject_map")
        self.subject_map = dict(subject_map)
        self.source_id = parse_model(Provenance, {"source": source_id}).source
        self.body_sites = dict(body_site_map or {})
        self.methods = dict(method_map or {})
        try:
            self.imported_at = instant(imported_at)
            local_day(self.imported_at, utc_offset_minutes)
        except ValueError:
            raise InputError("invalid_import_time") from None
        self.offset = utc_offset_minutes
        self.codes = dict(DEFAULT_CODES if code_map is None else code_map)
        self.revisions = dict(revision_map or {})

    def loads(self, text: str) -> CycleDataset:
        return self.from_mapping(loads(text, source_decimals=True))

    def load(self, path: str | Path) -> CycleDataset:
        return self.loads(read_text(path))

    def from_mapping(self, resource: Mapping[str, Any]) -> CycleDataset:
        if not isinstance(resource, Mapping):
            raise InputError("fhir_object_required")
        if resource.get("resourceType") == "Observation":
            observations = [resource]
        elif resource.get("resourceType") == "Bundle":
            if resource.get("type") not in ("collection", "searchset"):
                raise InputError("unsupported_fhir_bundle_type")
            links = resource.get("link", [])
            if not isinstance(links, list) or any(not isinstance(link, Mapping) for link in links):
                raise InputError("invalid_fhir_links")
            if any(link.get("relation") == "next" for link in links):
                raise InputError("incomplete_fhir_pagination")
            entries = resource.get("entry", [])
            if not isinstance(entries, list) or len(entries) > 50000:
                raise InputError("invalid_fhir_entries")
            observations = []
            for entry in entries:
                if not isinstance(entry, Mapping) or not isinstance(entry.get("resource"), Mapping):
                    raise InputError("missing_fhir_resource")
                observations.append(entry["resource"])
        else:
            raise InputError("unsupported_fhir_resource")
        events = []
        for row, observation in enumerate(observations, 1):
            try:
                events.append(self._observation(observation))
            except InputError as exc:
                raise InputError(exc.code, row=row) from None
            except (TypeError, AttributeError, ValueError, KeyError):
                raise InputError("invalid_fhir_observation", row=row) from None
        return CycleDataset(events=tuple(events))

    @staticmethod
    def _coded_field(item: Mapping[str, Any], name: str, mapping: Mapping[tuple[str, str], str]) -> str | None:
        if name not in item:
            return None
        coding = item[name].get("coding", [])
        values = {mapping[(c.get("system"), c.get("code"))] for c in coding
                  if isinstance(c, Mapping) and (c.get("system"), c.get("code")) in mapping}
        if len(values) != 1:
            raise InputError("unmapped_fhir_" + name.lower())
        return next(iter(values))

    def _observation(self, item: Mapping[str, Any]) -> Measurement:
        if item.get("resourceType") != "Observation":
            raise InputError("unsupported_fhir_resource")
        if item.get("status") not in ("final", "amended", "corrected"):
            raise InputError("unsupported_fhir_status")
        if "component" in item or "effectivePeriod" in item or "effectiveTiming" in item:
            raise InputError("unsupported_fhir_observation_shape")
        if any(str(k).startswith("value") and k != "valueQuantity" for k in item):
            raise InputError("unsupported_fhir_value_type")
        if "modifierExtension" in item:
            raise InputError("unhandled_fhir_modifier")
        raw_id = item.get("id")
        if not isinstance(raw_id, str) or not raw_id or len(raw_id) > 64:
            raise InputError("fhir_id_required")
        reference = item.get("subject", {}).get("reference")
        if reference not in self.subject_map:
            raise InputError("unmapped_fhir_subject")
        coding = item.get("code", {}).get("coding", [])
        matches = {self.codes[(c.get("system"), c.get("code"))] for c in coding
                   if isinstance(c, Mapping) and (c.get("system"), c.get("code")) in self.codes}
        if len(matches) != 1:
            raise InputError("unmapped_or_ambiguous_fhir_code")
        metric = next(iter(matches))
        measured = instant(item.get("effectiveDateTime"))
        reported = instant(item.get("issued", self.imported_at))
        quantity = item.get("valueQuantity")
        missing = item.get("dataAbsentReason")
        if quantity is not None and missing is not None:
            raise InputError("fhir_value_with_absence_reason")
        if quantity is not None:
            if not isinstance(quantity, Mapping) or quantity.get("comparator") is not None:
                raise InputError("unsupported_fhir_quantity")
            if quantity.get("system") != "http://unitsofmeasure.org":
                raise InputError("ucum_system_required")
            unit, value = quantity.get("code"), quantity.get("value")
            if type(value) is int:
                value = str(value)
            if not isinstance(value, str):
                raise InputError("exact_fhir_decimal_required")
            state, reason = "measured", None
        elif isinstance(missing, Mapping):
            # The unit is absent in FHIR. Use only the explicit canonical metric map.
            canonical = {"heart_rate": "/min", "body_temperature": "Cel"}
            if metric not in canonical:
                raise InputError("missing_fhir_unit_for_custom_metric")
            unit, value, state = canonical[metric], None, "missing"
            reasons = {c.get("code") for c in missing.get("coding", []) if isinstance(c, Mapping)
                       and c.get("system") == "http://terminology.hl7.org/CodeSystem/data-absent-reason"}
            if len(reasons) != 1 or not all(isinstance(r, str) for r in reasons):
                raise InputError("explicit_fhir_absence_reason_required")
            reason = next(iter(reasons))
        else:
            raise InputError("fhir_value_or_absence_required")
        source_key = sha256((self.source_id + "\0" + reference + "\0" + raw_id).encode()).hexdigest()[:32]
        return parse_model(Measurement, {
            "subject_id": self.subject_map[reference], "id": "fhir-" + source_key,
            "revision": self.revisions.get(raw_id, 1), "recorded_at": reported,
            "utc_offset_minutes": self.offset, "date": local_day(measured, self.offset),
            "metric": metric, "state": state, "value": value, "unit": unit,
            "measured_at": measured, "missing_reason": reason,
            "body_site": self._coded_field(item, "bodySite", self.body_sites),
            "method": self._coded_field(item, "method", self.methods),
            "provenance": Provenance(source=self.source_id, source_record_id=raw_id,
                                     imported_at=self.imported_at),
        })
