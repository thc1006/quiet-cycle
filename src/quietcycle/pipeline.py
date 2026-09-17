"""The public integration boundary. No network, logging, storage, or hidden clock."""
from __future__ import annotations

from collections.abc import Iterable
from fractions import Fraction

from .dates import day_difference

from .errors import InputError
from .features import DefaultFeatureBuilder, FeatureBuilder
from .ledger import snapshot
from .models import CycleDataset, Forecast, PipelineResult, Query
from .predictors import EmpiricalPredictor, Predictor
from .serialization import parse_model


class CyclePipeline:
    def __init__(self, *, predictor: Predictor | None = None,
                 feature_builder: FeatureBuilder | None = None) -> None:
        self.predictor = predictor if predictor is not None else EmpiricalPredictor()
        self.feature_builder = feature_builder if feature_builder is not None else DefaultFeatureBuilder()

    def run(self, dataset: CycleDataset, query: Query) -> PipelineResult:
        # Revalidate public objects, including objects built through model_construct/model_copy.
        dataset = parse_model(CycleDataset, dataset)
        query = parse_model(Query, query)
        return self._run_validated(dataset, query)

    def _run_validated(self, dataset: CycleDataset, query: Query) -> PipelineResult:
        selected = snapshot(dataset, query)
        features = self.feature_builder.build(selected, query)
        forecast = parse_model(Forecast, self.predictor.predict(features, query))
        if forecast.model_id != self.predictor.model_id or forecast.model_version != self.predictor.model_version:
            raise InputError("predictor_identity_mismatch")
        if any(point.date < query.as_of for point in forecast.distribution):
            raise InputError("predictor_returned_past_date")
        if forecast.status == "estimate":
            expected = sum((p.mass.as_fraction() for p in forecast.distribution
                            if 0 <= day_difference(p.date, query.as_of) < 3), Fraction())
            if forecast.within_three_days is None or forecast.within_three_days.as_fraction() != expected:
                raise InputError("near_term_mass_mismatch")
            if forecast.audit.anchor_date is not None and any(
                day_difference(p.date, forecast.audit.anchor_date) != p.cycle_length for p in forecast.distribution
            ):
                raise InputError("cycle_length_date_mismatch")
        if features.snapshot_sha256 != selected.sha256:
            raise InputError("feature_provenance_mismatch")
        return PipelineResult(
            subject_id=query.subject_id, as_of=query.as_of, cutoff=query.cutoff,
            snapshot_sha256=selected.sha256, forecast=forecast,
            measurements=features.measurements, symptoms=features.symptoms,
            observation_count=len(selected.events), feature_builder_id=self.feature_builder.builder_id,
            used_features=self.predictor.used_features,
        )

    def run_many(self, dataset: CycleDataset, queries: Iterable[Query]) -> tuple[PipelineResult, ...]:
        """Preserve caller order. Each query selects exactly one pseudonymous subject."""
        dataset = parse_model(CycleDataset, dataset)
        results: list[PipelineResult] = []
        for query in queries:
            if len(results) >= 10000:
                raise InputError("batch_too_large")
            results.append(self._run_validated(dataset, parse_model(Query, query)))
        return tuple(results)
