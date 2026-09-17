> This card describes the retained historical baseline. For the fitted learner, see [MODEL_CARD_MULTIFACTOR.md](MODEL_CARD_MULTIFACTOR.md).

# Model card: empirical-triangle-v1

Status: uncalibrated deterministic research baseline. No clinical validation,
regulatory clearance, real-world accuracy claim, or universal-population claim.

The default policy uses the most recent 3–6 explicitly confirmed consecutive
intervals. Its engineering support is 10–180 days; bandwidth is 2 days; maximum
observed spread is 20 days; remaining original model mass must be at least 100,000
ppm and at least 3 supported dates must remain. These are disclosed heuristic
settings, not clinical definitions of a normal cycle.

For each observed length c, integer weights bandwidth+1-|k| are added at c+k.
The model retains possible lengths after explicitly confirmed completed no-onset
days. It does not interpret absent records as those confirmations. If unresolved
model mass lies in the past, the model abstains rather than silently moving the
forecast forward. Exhausted/weak support, invalid continuity, uncertain anchors,
context changes, and unsuitable scope also cause abstention.

The mathematical baseline is ported from the supplied 0.1.0 JavaScript project;
300 frozen-reference cases compare equivalent requests. Exact arithmetic checks
are not clinical outcome validation. Agreement between implementations can still
preserve a shared modeling limitation.

## What is not learned

No population prior, hormone threshold, wearable coefficient, or symptom weight is
fitted. No clinical dataset is distributed. Temperature/heart-rate/etc. normalize
through the pipeline, but the default predictor uses onset/no-onset/context only.
Symptoms produce descriptive counts over recorded days, not risk estimates.
The separate duration model is executable with caller parameters, not a pretrained
predictor or a reproduction of a published study's accuracy.

## Evaluation needed before consequential use

Freeze prediction cutoff and availability times. Separate future data from the
features at prediction time, even when it was later entered retrospectively.
Compare at the same lead times against simple historical baselines. Report MAE,
interval coverage and width, tail errors, abstention frequency, and subgroup results.
Do not exclude difficult cases silently or compare retrospective phase labels with
prospective next-onset prediction. Device changes and sampling/missingness patterns
must be evaluated. Clinical interpretation requires appropriate expertise and study
oversight; this package does not supply either.

The research conformal helper implements an order statistic. It cannot make
exchangeability true in an individual's evolving time series. A requested 90%
model interval is not evidence of 90% empirical coverage.
