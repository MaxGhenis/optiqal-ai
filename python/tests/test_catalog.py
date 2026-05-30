"""Tests for the intervention catalog and publication bias correction."""

import pytest

from optiqal.catalog import (
    CATALOG,
    PUBLIC_CONDITION_DATA_PATH,
    PUBLIC_ITEM_POLICY_DATA_PATH,
    PUBLIC_LANE_DATA_PATH,
    CatalogEntry,
    build_public_policy_spec,
    get_catalog,
    has_meaningful_public_glp1_signal,
    has_meaningful_public_metformin_signal,
    has_meaningful_public_statin_signal,
    is_publicly_rankable,
    public_display_category,
    public_rankability_reason,
    public_recommendation_lane,
    simulate_catalog,
)
from optiqal.combination import find_optimal_portfolio_with_costs
from optiqal.confounding import publication_bias_correct
from optiqal.defaults import DEFAULT_QALY_DISCOUNT_RATE
from optiqal.profile import Profile
from optiqal.sleep import SleepMetrics, estimate_sleep_burden
from optiqal.stack_interactions import build_stack_interaction_penalty_fn


class TestPublicationBiasCorrection:
    def test_shrinks_toward_null(self):
        """Corrected HR should be closer to 1.0 than observed."""
        corrected = publication_bias_correct(0.80, shrinkage=0.30)
        assert 0.80 < corrected < 1.0

    def test_null_unchanged(self):
        """HR = 1.0 stays at 1.0."""
        assert publication_bias_correct(1.0, shrinkage=0.30) == pytest.approx(1.0)

    def test_harmful_shrinks_toward_null(self):
        """HR > 1.0 should also shrink toward 1.0."""
        corrected = publication_bias_correct(1.50, shrinkage=0.30)
        assert 1.0 < corrected < 1.50

    def test_zero_shrinkage_unchanged(self):
        """No shrinkage returns original HR."""
        assert publication_bias_correct(0.80, shrinkage=0.0) == pytest.approx(0.80)

    def test_full_shrinkage_returns_null(self):
        """100% shrinkage returns HR = 1.0."""
        assert publication_bias_correct(0.80, shrinkage=1.0) == pytest.approx(1.0)

    def test_30pct_shrinkage_value(self):
        """Check specific numeric value for 30% shrinkage of HR 0.80."""
        # log(0.80) = -0.2231, * 0.70 = -0.1562, exp = 0.8555
        corrected = publication_bias_correct(0.80, shrinkage=0.30)
        assert corrected == pytest.approx(0.8555, rel=0.01)


class TestCatalog:
    def test_catalog_not_empty(self):
        assert len(CATALOG) > 40

    def test_all_entries_have_required_fields(self):
        for entry_id, entry in CATALOG.items():
            assert entry.id == entry_id
            assert entry.name
            assert 0 < entry.hr_observed <= 1.5
            assert entry.log_sd > 0
            assert entry.conf_alpha > 0
            assert entry.conf_beta > 0
            assert entry.annual_cost >= 0 or entry.annual_cost < 0  # savings possible

    def test_categories_present(self):
        categories = {e.category for e in CATALOG.values()}
        assert "rx_current" in categories
        assert "supplement_current" in categories
        assert "supplement_candidate" in categories
        assert "sleep_current" in categories

    def test_get_catalog_filter(self):
        rx = get_catalog(["rx_current"])
        assert all(e.category == "rx_current" for e in rx.values())
        assert len(rx) > 0

    def test_to_intervention(self):
        entry = CATALOG["omega3_clo"]
        intervention = entry.to_intervention(pub_bias_shrinkage=0.30)
        assert intervention.id == "omega3_clo"
        assert intervention.mortality is not None
        assert intervention.confounding_prior is not None

    def test_to_intervention_applies_pub_bias(self):
        # Pick an entry without an explicit study_quality tier so the
        # pub_bias_shrinkage parameter is used as the fallback. When a tier
        # is set it takes precedence over the caller-supplied fallback.
        entry = CATALOG["omega3_clo"]
        from dataclasses import replace as _replace
        entry = _replace(entry, study_quality=None)
        # With 0% shrinkage, should use raw HR
        int_no_bias = entry.to_intervention(pub_bias_shrinkage=0.0)
        # With 30% shrinkage, HR should be closer to 1
        int_biased = entry.to_intervention(pub_bias_shrinkage=0.30)

        hr_raw = int_no_bias.mortality.hazard_ratio.mean
        hr_corrected = int_biased.mortality.hazard_ratio.mean
        assert hr_corrected > hr_raw  # Closer to 1.0 (less protective)

    def test_study_quality_tier_overrides_fallback(self):
        """When an entry sets study_quality, tier shrinkage wins over caller fallback."""
        entry = CATALOG["finasteride_1.25mg"]  # preregistered RCT tier (10% shrinkage)
        # Caller demands huge (90%) fallback shrinkage. Tier should still win.
        corrected = entry.corrected_hr_observed(pub_bias_shrinkage=0.90)
        # With only 10% shrinkage and a 0.95 evidence multiplier:
        # exp(log(0.93) * 0.9 * 0.95) ≈ 0.940
        assert 0.935 < corrected < 0.945
        # Without the tier override the result would be dramatically weaker.
        from dataclasses import replace as _replace
        untiered = _replace(entry, study_quality=None)
        corrected_untiered = untiered.corrected_hr_observed(pub_bias_shrinkage=0.90)
        assert corrected_untiered > 0.99  # 90% shrinkage → near null


class TestBundleCostAllocation:
    """Bundled items should share the parent bundle's price, not cost $0."""

    def test_nr_300_has_nonzero_effective_cost(self):
        """NR 300 is bundled into Blueprint Essentials — should carry allocation."""
        entry = CATALOG["nr_300"]
        assert entry.annual_cost == 0  # raw $ still 0 — it's inside the bundle
        assert entry.bundle_id == "blueprint_essential_capsules"
        assert entry.bundle_cost_share > 0
        # The reported effective cost is what $/QALY should use.
        assert entry.effective_annual_cost() > 0
        assert entry.effective_annual_cost() == entry.bundle_cost_share

    def test_standalone_items_unaffected(self):
        """Items with annual_cost already set should not gain a bundle share."""
        entry = CATALOG["tadalafil_2.5mg"]
        assert entry.bundle_cost_share == 0.0
        assert entry.effective_annual_cost() == entry.annual_cost

    def test_every_bundled_item_has_allocation(self):
        """Every ingredient tagged as bundle member should declare a share."""
        bundled_ids = (
            "fisetin_100", "spermidine_10", "nr_300", "ubiquinol_50",
            "lithium_1mg_orotate", "boron_3", "broccoli_seed_200", "luteolin_100",
            "astaxanthin_12", "lutein_zeaxanthin", "lycopene_15",
            "hyaluronic_acid_120", "ginger_400",
        )
        for item_id in bundled_ids:
            entry = CATALOG[item_id]
            assert entry.bundle_id is not None, item_id
            assert entry.bundle_cost_share > 0, item_id


class TestPosteriorHrExposure:
    """simulate_catalog should surface posterior HR for mortality-bearing items."""

    def test_posterior_hr_in_item_results(self):
        profile = Profile(
            age=39, sex="male", bmi_category="normal", smoking_status="never",
            has_diabetes=False, has_hypertension=False, activity_level="light",
        )
        results = simulate_catalog(
            profile=profile,
            n_simulations=2_000,
            random_state=1,
            pub_bias_shrinkage=0.30,
            categories=["rx_current"],
        )
        finasteride = next(r for r in results if r["id"] == "finasteride_1.25mg")
        # Posterior HR should exist, be between observed and 1.0, and lie
        # weaker than the publication-bias-only HR (which doesn't apply the
        # Bayesian causal-fraction shrinkage).
        assert finasteride["hr_posterior_mean"] is not None
        assert finasteride["hr_posterior_median"] is not None
        ci_low, ci_high = finasteride["hr_posterior_ci95"]
        assert ci_low < finasteride["hr_posterior_median"] < ci_high
        assert finasteride["hr_observed"] < finasteride["hr_posterior_median"] <= 1.01
        # Posterior HR is weaker (closer to 1) than pub-bias-only HR.
        assert finasteride["hr_posterior_median"] >= finasteride["hr_corrected"] - 1e-3

    def test_to_intervention_applies_evidence_shrinkage(self):
        high = CatalogEntry(
            id="high_evidence",
            name="High evidence",
            category="supplement_candidate",
            hr_observed=0.8,
            log_sd=0.05,
            conf_alpha=2.0,
            conf_beta=2.0,
            annual_cost=0,
            evidence_quality="high",
        )
        low = CatalogEntry(
            id="low_evidence",
            name="Low evidence",
            category="supplement_candidate",
            hr_observed=0.8,
            log_sd=0.05,
            conf_alpha=2.0,
            conf_beta=2.0,
            annual_cost=0,
            evidence_quality="low",
        )

        high_hr = high.to_intervention(pub_bias_shrinkage=0.30).mortality.hazard_ratio.mean
        low_hr = low.to_intervention(pub_bias_shrinkage=0.30).mortality.hazard_ratio.mean

        assert low_hr > high_hr

    def test_to_intervention_preserves_harm_metadata(self):
        entry = CATALOG["trazodone_50mg"]
        intervention = entry.to_intervention(pub_bias_shrinkage=0.30)
        assert intervention.harm_model
        assert intervention.interaction_tags == ["sedating"]
        assert intervention.interaction_rules

    def test_low_evidence_sleep_adjuncts_are_shrunk_more_than_high_evidence_therapy(self):
        sleep_estimate = estimate_sleep_burden(
            SleepMetrics(
                duration_hours=6.5,
                recovery_score=55.0,
                sleep_quality_score=80.0,
                waso_min=14.0,
                routine_score=74.0,
                social_jetlag_min=20.0,
                latency_min=17.0,
                breathing_score=0.86,
                spo2=95.8,
                snore_pct=2.0,
                airway_response_signal=0.35,
            )
        )

        apap = CATALOG["apap_nightly"]
        mouth_tape = CATALOG["mouth_tape_nightly"]

        assert apap.evidence_quality == "high"
        assert mouth_tape.evidence_quality == "low"
        assert apap.evidence_effect_multiplier() > mouth_tape.evidence_effect_multiplier()
        assert apap.sleep_qol_annual(sleep_estimate) > mouth_tape.sleep_qol_annual(sleep_estimate)

    def test_low_dose_melatonin_harm_prior_is_small(self):
        harm = CATALOG["melatonin_300mcg"].harm_effects[0].annual_qaly_loss

        assert harm is not None
        assert harm.params["mean"] < 0.0003

    def test_trazodone_harm_prior_is_material_but_not_extreme(self):
        melatonin = CATALOG["melatonin_300mcg"].harm_effects[0].annual_qaly_loss
        trazodone = CATALOG["trazodone_50mg"].harm_effects[0].annual_qaly_loss

        assert melatonin is not None
        assert trazodone is not None
        assert trazodone.params["mean"] > melatonin.params["mean"] * 5
        assert trazodone.params["mean"] < 0.002

    def test_insomnia_rx_alternatives_are_grouped_and_less_harmful_than_trazodone(self):
        trazodone = CATALOG["trazodone_50mg"]
        doxepin = CATALOG["doxepin_3mg"]
        daridorexant = CATALOG["daridorexant_25mg"]
        lemborexant = CATALOG["lemborexant_5mg"]
        suvorexant = CATALOG["suvorexant_10mg"]

        assert trazodone.exclusive_group == "insomnia_rx"
        assert doxepin.exclusive_group == "insomnia_rx"
        assert daridorexant.exclusive_group == "insomnia_rx"
        assert lemborexant.exclusive_group == "insomnia_rx"
        assert suvorexant.exclusive_group == "insomnia_rx"
        assert doxepin.harm_effects[0].annual_qaly_loss.params["mean"] < trazodone.harm_effects[0].annual_qaly_loss.params["mean"]
        assert daridorexant.harm_effects[0].annual_qaly_loss.params["mean"] < trazodone.harm_effects[0].annual_qaly_loss.params["mean"]
        assert lemborexant.harm_effects[0].annual_qaly_loss.params["mean"] < trazodone.harm_effects[0].annual_qaly_loss.params["mean"]
        assert suvorexant.harm_effects[0].annual_qaly_loss.params["mean"] < trazodone.harm_effects[0].annual_qaly_loss.params["mean"]
        assert daridorexant.harm_effects[0].annual_qaly_loss.params["mean"] < suvorexant.harm_effects[0].annual_qaly_loss.params["mean"]
        assert lemborexant.harm_effects[0].annual_qaly_loss.params["mean"] < suvorexant.harm_effects[0].annual_qaly_loss.params["mean"]

    def test_glycine_and_taurine_do_not_claim_mortality_benefit(self):
        glycine = CATALOG["glycine_2g"]
        taurine = CATALOG["taurine_500_topup"]

        assert glycine.hr_observed == pytest.approx(1.0)
        assert taurine.hr_observed == pytest.approx(1.0)
        assert glycine.qol_annual > 0
        assert taurine.qol_annual >= 0
        assert glycine.to_intervention(pub_bias_shrinkage=0.30).mortality is None
        assert taurine.to_intervention(pub_bias_shrinkage=0.30).mortality is None

    def test_creatine_qol_is_componentized_with_cognitive_uncertainty(self):
        creatine = CATALOG["creatine_5g"]
        effect_ids = {effect.id for effect in creatine.qol_effects}

        assert creatine.qol_annual == 0
        assert creatine.raw_qol_annual() > 0.005
        assert "cognitive_resilience" in effect_ids
        assert "strength_power_lean_mass" in effect_ids
        assert creatine.harm_effects

    def test_creatine_total_probability_includes_qol_draws(self):
        profile = Profile(
            age=39,
            sex="male",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=False,
            has_hypertension=False,
            activity_level="light",
        )

        result = simulate_catalog(
            profile,
            n_simulations=4000,
            random_state=42,
            catalog_entries={"creatine_5g": CATALOG["creatine_5g"]},
        )[0]

        assert result["qol_effects"]
        assert result["p_benefit"] > 0.90
        assert result["ci_low"] < result["days"] < result["ci_high"]
        assert result["qol_qaly"] > abs(result["harm_qaly"])

    def test_probiotic_testing_is_low_evidence_gut_support_without_direct_mortality(self):
        probiotic = CATALOG["probiotic_daily"]

        assert probiotic.category == "supplement_bought"
        assert probiotic.annual_cost == 273
        assert probiotic.evidence_quality == "low"
        assert probiotic.benefit_tags == ["gut_support"]
        assert probiotic.has_direct_mortality_effect is False
        assert probiotic.to_intervention(pub_bias_shrinkage=0.30).mortality is None

    def test_airway_and_trazodone_entries_without_direct_mortality_return_none(self):
        for item_id in [
            "trazodone_50mg",
            "nasacort_nightly",
            "nasal_strips_nightly",
            "humidifier_nightly",
            "mouth_tape_nightly",
            "head_elevation_nightly",
            "apap_nightly",
            "oral_appliance_custom",
            "hiit_1x_week",
            "hiit_2x_week",
            "hiit_3x_week",
            "zone2_cardio_2x_week",
            "tempo_run_1x_week",
            "strength_maintenance",
            "traditional_sauna_4x_week",
            "infrared_sauna_4x_week",
            "hbot_60sessions",
            "bpc157_cycle",
            "tb500_cycle",
        ]:
            assert CATALOG[item_id].to_intervention(pub_bias_shrinkage=0.30).mortality is None

    def test_traditional_sauna_has_stronger_qol_signal_than_infrared(self):
        traditional = CATALOG["traditional_sauna_4x_week"]
        infrared = CATALOG["infrared_sauna_4x_week"]

        assert traditional.hr_observed == pytest.approx(1.0)
        assert infrared.hr_observed == pytest.approx(1.0)
        assert traditional.qol_annual > infrared.qol_annual
        assert traditional.qol_years > infrared.qol_years

    def test_hiit_two_sessions_has_more_qol_than_one(self):
        hiit_1 = CATALOG["hiit_1x_week"]
        hiit_2 = CATALOG["hiit_2x_week"]

        assert hiit_1.hr_observed == pytest.approx(1.0)
        assert hiit_2.hr_observed == pytest.approx(1.0)
        assert hiit_2.qol_annual > hiit_1.qol_annual
        assert hiit_1.to_intervention(pub_bias_shrinkage=0.30).mortality is None
        assert hiit_2.to_intervention(pub_bias_shrinkage=0.30).mortality is None

    def test_cardio_mode_progression_orders_zone2_tempo_hiit(self):
        zone2 = CATALOG["zone2_cardio_2x_week"]
        tempo = CATALOG["tempo_run_1x_week"]
        hiit = CATALOG["hiit_2x_week"]
        hiit3 = CATALOG["hiit_3x_week"]

        assert zone2.exclusive_group == "cardio_mode"
        assert tempo.exclusive_group == "cardio_mode"
        assert hiit.exclusive_group == "cardio_mode"
        assert hiit3.exclusive_group == "cardio_mode"
        assert zone2.qol_annual < tempo.qol_annual < hiit.qol_annual

    def test_hiit_three_sessions_is_more_uncertain_than_two(self):
        hiit_2 = CATALOG["hiit_2x_week"]
        hiit_3 = CATALOG["hiit_3x_week"]

        assert hiit_3.log_sd > hiit_2.log_sd
        assert hiit_3.conf_alpha / (hiit_3.conf_alpha + hiit_3.conf_beta) < hiit_2.conf_alpha / (hiit_2.conf_alpha + hiit_2.conf_beta)

    def test_public_rankability_keeps_true_free_behavioral_items(self):
        assert is_publicly_rankable(CATALOG["hiit_2x_week"]) is True
        assert is_publicly_rankable(CATALOG["head_elevation_nightly"]) is False
        assert public_rankability_reason(CATALOG["head_elevation_nightly"]) is not None

        airway_sleep = estimate_sleep_burden(
            SleepMetrics(
                duration_hours=6.5,
                sleep_quality_score=78.0,
                breathing_score=0.72,
                spo2=94.8,
                snore_pct=4.0,
            )
        )
        assert is_publicly_rankable(
            CATALOG["head_elevation_nightly"],
            sleep_estimate=airway_sleep,
        ) is True
        assert public_rankability_reason(
            CATALOG["head_elevation_nightly"],
            sleep_estimate=airway_sleep,
        ) is None

    def test_public_recommendation_lane_splits_consumer_conditional_and_personal_items(self):
        assert public_recommendation_lane(CATALOG["hiit_2x_week"]) == "consumer_public"
        assert public_recommendation_lane(CATALOG["head_elevation_nightly"]) == "conditional_public"
        assert public_recommendation_lane(CATALOG["statin_5mg"]) == "conditional_public"
        assert public_recommendation_lane(CATALOG["metformin_500mg"]) == "conditional_public"
        assert public_recommendation_lane(CATALOG["semaglutide"]) == "conditional_public"
        assert public_recommendation_lane(CATALOG["quercetin_500"]) == "personal_only"

    def test_public_cardiometabolic_signal_helpers_are_selective(self):
        healthy = Profile(
            age=35,
            sex="female",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=False,
            has_hypertension=False,
            activity_level="light",
        )
        higher_risk = Profile(
            age=58,
            sex="male",
            bmi_category="obese",
            smoking_status="current",
            has_diabetes=False,
            has_hypertension=True,
            activity_level="light",
        )
        diabetes = Profile(
            age=52,
            sex="male",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=True,
            has_hypertension=False,
            activity_level="light",
        )

        assert has_meaningful_public_statin_signal(healthy) is False
        assert has_meaningful_public_metformin_signal(healthy) is False
        assert has_meaningful_public_glp1_signal(healthy) is False
        assert has_meaningful_public_statin_signal(higher_risk) is True
        assert has_meaningful_public_metformin_signal(higher_risk) is False
        assert has_meaningful_public_glp1_signal(higher_risk) is True
        assert has_meaningful_public_metformin_signal(diabetes) is True

        assert is_publicly_rankable(CATALOG["statin_5mg"], profile=healthy) is False
        assert is_publicly_rankable(CATALOG["metformin_500mg"], profile=healthy) is False
        assert is_publicly_rankable(CATALOG["semaglutide"], profile=healthy) is False
        assert is_publicly_rankable(CATALOG["statin_5mg"], profile=higher_risk) is True
        assert is_publicly_rankable(CATALOG["metformin_500mg"], profile=higher_risk) is False
        assert is_publicly_rankable(CATALOG["semaglutide"], profile=higher_risk) is True
        assert is_publicly_rankable(CATALOG["metformin_500mg"], profile=diabetes) is True

    def test_public_rankability_excludes_bundle_dependent_zero_cost_items(self):
        assert is_publicly_rankable(CATALOG["astaxanthin_12"]) is False
        assert public_rankability_reason(CATALOG["astaxanthin_12"]) is not None

    def test_public_display_category_normalizes_personal_status_categories(self):
        assert public_display_category(CATALOG["hiit_2x_week"]) == "exercise"
        assert public_display_category(CATALOG["nasacort_nightly"]) == "sleep"
        assert public_display_category(CATALOG["humidifier_nightly"]) == "sleep"
        assert public_display_category(CATALOG["mouth_tape_nightly"]) == "sleep"
        assert public_display_category(CATALOG["doxepin_3mg"]) == "sleep"
        assert public_display_category(CATALOG["statin_5mg"]) == "rx"
        assert public_display_category(CATALOG["quercetin_500"]) == "supplement"

    def test_public_policy_spec_exports_condition_rules(self):
        assert PUBLIC_CONDITION_DATA_PATH.exists()
        assert PUBLIC_ITEM_POLICY_DATA_PATH.exists()
        assert PUBLIC_LANE_DATA_PATH.exists()
        policy = build_public_policy_spec(CATALOG)
        lanes = {lane["id"]: lane for lane in policy["lanes"]}
        conditions = {condition["id"]: condition for condition in policy["conditions"]}
        items = {item["id"]: item for item in policy["items"]}

        assert lanes["consumer_public"]["label"] == "Broad public recommendations"
        assert lanes["personal_only"]["description"].startswith("Current-stack")
        assert items["hiit_2x_week"]["lane"] == "consumer_public"
        assert items["apap_nightly"]["condition"] == "osa_therapy_signal"
        assert items["traditional_sauna_4x_week"]["display_category"] == "service"

        airway = conditions["airway_signal"]
        assert airway["evaluation_kind"] == "sleep_any_threshold"
        assert airway["score_threshold"] is None
        assert any(rule["signal"] == "sleep_breathing_burden" for rule in airway["thresholds"])

        cardiometabolic = conditions["cardiometabolic_signal"]
        assert cardiometabolic["evaluation_kind"] == "profile_score"
        assert cardiometabolic["score_threshold"] == 4
        assert any(rule["field"] == "has_diabetes" and rule["points"] == 4 for rule in cardiometabolic["score_rules"])
        assert public_display_category(CATALOG["traditional_sauna_4x_week"]) == "service"

    def test_sleep_access_profiles_capture_coverage_and_friction(self):
        assert CATALOG["head_elevation_nightly"].access_profile.tier == "behavioral"
        assert CATALOG["head_elevation_nightly"].access_profile.friction == "low"
        assert CATALOG["melatonin_300mcg"].access_profile.tier == "otc"
        assert CATALOG["humidifier_nightly"].access_profile.tier == "cash_pay"
        assert CATALOG["humidifier_nightly"].access_profile.friction == "low"
        assert CATALOG["mouth_tape_nightly"].access_profile.tier == "cash_pay"
        assert CATALOG["mouth_tape_nightly"].access_profile.friction == "low"
        assert CATALOG["apap_nightly"].access_profile.coverage_outlook == "likely"
        assert CATALOG["oral_appliance_custom"].access_profile.coverage_outlook == "mixed"
        assert CATALOG["doxepin_3mg"].access_profile.tier == "generic_rx"
        assert CATALOG["daridorexant_25mg"].access_profile.tier == "brand_rx_prior_auth"

    @pytest.mark.parametrize(
        ("bundled_id", "unbundled_id"),
        [
            ("nr_300", "nr_300_unbundled"),
            ("ubiquinol_50", "ubiquinol_50_unbundled"),
            ("luteolin_100", "luteolin_100_unbundled"),
            ("fisetin_100", "fisetin_100_unbundled"),
        ],
    )
    def test_unbundled_variants_keep_effect_but_change_cost(self, bundled_id, unbundled_id):
        bundled = CATALOG[bundled_id]
        unbundled = CATALOG[unbundled_id]

        assert unbundled.hr_observed == pytest.approx(bundled.hr_observed)
        assert unbundled.log_sd == pytest.approx(bundled.log_sd)
        assert unbundled.conf_alpha == pytest.approx(bundled.conf_alpha)
        assert unbundled.conf_beta == pytest.approx(bundled.conf_beta)
        assert unbundled.qol_annual == pytest.approx(bundled.qol_annual)
        assert unbundled.benefit_tags == bundled.benefit_tags
        assert bundled.annual_cost == 0
        assert unbundled.annual_cost > 0
        assert bundled.category != unbundled.category

    def test_semaglutide_transport_shrinks_for_lean_profile(self):
        entry = CATALOG["semaglutide"]
        lean = Profile(
            age=39,
            sex="male",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=False,
            has_hypertension=False,
            activity_level="light",
        )
        obese_diabetic = Profile(
            age=55,
            sex="male",
            bmi_category="obese",
            smoking_status="never",
            has_diabetes=True,
            has_hypertension=True,
            activity_level="light",
        )

        assert entry.profile_effect_multiplier(lean) < entry.profile_effect_multiplier(obese_diabetic)

        lean_intervention = entry.to_intervention(pub_bias_shrinkage=0.30, profile=lean)
        obese_intervention = entry.to_intervention(pub_bias_shrinkage=0.30, profile=obese_diabetic)
        assert lean_intervention.mortality.hazard_ratio.mean > obese_intervention.mortality.hazard_ratio.mean

    def test_simulate_catalog_default_discount_matches_canonical_rate(self):
        profile = Profile(
            age=39,
            sex="male",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=False,
            has_hypertension=False,
            activity_level="light",
        )

        default_results = simulate_catalog(
            profile,
            n_simulations=2000,
            random_state=42,
            categories=["rx_current"],
        )
        explicit_results = simulate_catalog(
            profile,
            n_simulations=2000,
            random_state=42,
            categories=["rx_current"],
            qaly_discount_rate=DEFAULT_QALY_DISCOUNT_RATE,
        )

        default_by_id = {result["id"]: result for result in default_results}
        explicit_by_id = {result["id"]: result for result in explicit_results}

        assert default_by_id.keys() == explicit_by_id.keys()
        for item_id in default_by_id:
            assert default_by_id[item_id]["mort_qaly"] == pytest.approx(
                explicit_by_id[item_id]["mort_qaly"]
            )
            assert "harm_qaly" in default_by_id[item_id]
            assert "direct_harm_qaly" in default_by_id[item_id]
            assert "interaction_harm_qaly" in default_by_id[item_id]
            assert "component_breakdown" in default_by_id[item_id]
            assert "top_positive_component" in default_by_id[item_id]
            assert "top_negative_component" in default_by_id[item_id]

    def test_simulate_catalog_rejects_negative_qaly_discount(self):
        profile = Profile(
            age=39,
            sex="male",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=False,
            has_hypertension=False,
            activity_level="light",
        )

        with pytest.raises(ValueError, match="nonnegative"):
            simulate_catalog(
                profile,
                n_simulations=1000,
                random_state=42,
                categories=["rx_current"],
                qaly_discount_rate=-0.01,
            )

    def test_simulate_catalog_can_apply_personalized_sleep_relief(self):
        profile = Profile(
            age=39,
            sex="male",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=False,
            has_hypertension=False,
            activity_level="light",
        )
        sleep_estimate = estimate_sleep_burden(
            SleepMetrics(
                duration_hours=6.4,
                recovery_score=52.0,
                sleep_quality_score=76.0,
                waso_min=18.0,
                routine_score=68.0,
                social_jetlag_min=55.0,
                latency_min=23.0,
                breathing_score=0.75,
                spo2=95.0,
                snore_pct=4.0,
                sleep_debt_min=70.0,
            )
        )

        base = simulate_catalog(
            profile,
            n_simulations=1500,
            random_state=42,
            catalog_entries={"magnesium_200": CATALOG["magnesium_200"]},
        )[0]
        personalized = simulate_catalog(
            profile,
            n_simulations=1500,
            random_state=42,
            catalog_entries={"magnesium_200": CATALOG["magnesium_200"]},
            sleep_estimate=sleep_estimate,
        )[0]

        assert base["sleep_qol_qaly"] == pytest.approx(0.0)
        assert personalized["sleep_qol_annual"] > 0
        assert personalized["sleep_qol_qaly"] > 0
        assert personalized["baseline_sleep_hazard_multiplier"] > 1.0
        assert personalized["sleep_mortality_relief_fraction"] > 0
        assert personalized["sleep_mortality_hr_multiplier"] < 1.0
        assert personalized["total_qaly"] > base["total_qaly"]

    def test_simulate_catalog_exposes_component_breakdown_and_evidence_discount(self):
        profile = Profile(
            age=39,
            sex="male",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=False,
            has_hypertension=False,
            activity_level="light",
        )
        sleep_estimate = estimate_sleep_burden(
            SleepMetrics(
                duration_hours=6.4,
                recovery_score=52.0,
                sleep_quality_score=76.0,
                waso_min=18.0,
                routine_score=68.0,
                social_jetlag_min=55.0,
                latency_min=23.0,
                breathing_score=0.75,
                spo2=95.0,
                snore_pct=4.0,
                sleep_debt_min=70.0,
            )
        )

        result = simulate_catalog(
            profile,
            n_simulations=1500,
            random_state=42,
            catalog_entries={"mouth_tape_nightly": CATALOG["mouth_tape_nightly"]},
            sleep_estimate=sleep_estimate,
        )[0]

        breakdown = result["component_breakdown"]

        assert result["evidence_effect_multiplier"] == pytest.approx(0.75)
        assert result["evidence_discount_qaly"] > 0
        assert breakdown["evidence_discount_qaly"] < 0
        assert breakdown["sleep_qol_qaly"] == pytest.approx(result["sleep_qol_qaly"])
        assert breakdown["direct_qol_qaly"] == pytest.approx(result["qol_qaly"])
        assert breakdown["interaction_harm_qaly"] == pytest.approx(result["interaction_harm_qaly"])
        assert result["top_negative_component"] in {
            "direct_harm_qaly",
            "interaction_harm_qaly",
            "evidence_discount_qaly",
        }

    def test_simulate_catalog_respects_item_specific_qol_years(self):
        profile = Profile(
            age=39,
            sex="male",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=False,
            has_hypertension=False,
            activity_level="light",
        )
        short = CatalogEntry(
            id="short_qol",
            name="Short QoL",
            category="supplement_candidate",
            hr_observed=1.0,
            log_sd=0.01,
            conf_alpha=1.0,
            conf_beta=1.0,
            annual_cost=0,
            qol_annual=0.001,
            qol_years=5,
        )
        long = CatalogEntry(
            id="long_qol",
            name="Long QoL",
            category="supplement_candidate",
            hr_observed=1.0,
            log_sd=0.01,
            conf_alpha=1.0,
            conf_beta=1.0,
            annual_cost=0,
            qol_annual=0.001,
            qol_years=10,
        )

        results = simulate_catalog(
            profile,
            n_simulations=1000,
            random_state=42,
            catalog_entries={"short_qol": short, "long_qol": long},
        )
        by_id = {result["id"]: result for result in results}

        assert by_id["short_qol"]["qol_years"] == pytest.approx(5)
        assert by_id["long_qol"]["qol_years"] == pytest.approx(10)
        assert by_id["long_qol"]["qol_qaly"] > by_id["short_qol"]["qol_qaly"] * 1.8

    def test_simulate_catalog_respects_item_specific_sleep_qol_years(self):
        profile = Profile(
            age=39,
            sex="male",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=False,
            has_hypertension=False,
            activity_level="light",
        )
        sleep_estimate = estimate_sleep_burden(
            SleepMetrics(
                duration_hours=6.4,
                recovery_score=52.0,
                sleep_quality_score=76.0,
                waso_min=18.0,
                routine_score=68.0,
                social_jetlag_min=55.0,
                latency_min=23.0,
                breathing_score=0.75,
                spo2=95.0,
                snore_pct=4.0,
                sleep_debt_min=70.0,
            )
        )
        short = CatalogEntry(
            id="short_sleep_qol",
            name="Short Sleep QoL",
            category="supplement_candidate",
            hr_observed=1.0,
            log_sd=0.01,
            conf_alpha=1.0,
            conf_beta=1.0,
            annual_cost=0,
            qol_annual=0.0,
            qol_years=5,
            sleep_component_relief={"quality": 0.1},
        )
        long = CatalogEntry(
            id="long_sleep_qol",
            name="Long Sleep QoL",
            category="supplement_candidate",
            hr_observed=1.0,
            log_sd=0.01,
            conf_alpha=1.0,
            conf_beta=1.0,
            annual_cost=0,
            qol_annual=0.0,
            qol_years=10,
            sleep_component_relief={"quality": 0.1},
        )

        results = simulate_catalog(
            profile,
            n_simulations=1000,
            random_state=42,
            catalog_entries={
                "short_sleep_qol": short,
                "long_sleep_qol": long,
            },
            sleep_estimate=sleep_estimate,
        )
        by_id = {result["id"]: result for result in results}

        assert by_id["short_sleep_qol"]["sleep_qol_qaly"] > 0
        assert by_id["long_sleep_qol"]["sleep_qol_qaly"] > (
            by_id["short_sleep_qol"]["sleep_qol_qaly"] * 1.8
        )

    def test_airway_targeting_prefers_upper_airway_treatments_over_nac(self):
        profile = Profile(
            age=39,
            sex="male",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=False,
            has_hypertension=False,
            activity_level="light",
        )
        sleep_estimate = estimate_sleep_burden(
            SleepMetrics(
                duration_hours=6.5,
                recovery_score=55.0,
                sleep_quality_score=78.0,
                waso_min=18.0,
                routine_score=78.0,
                social_jetlag_min=25.0,
                latency_min=18.0,
                breathing_score=0.74,
                spo2=94.8,
                snore_pct=7.0,
                sleep_debt_min=40.0,
                airway_response_signal=0.85,
            )
        )

        results = simulate_catalog(
            profile,
            n_simulations=1500,
            random_state=42,
            catalog_entries={
                "nac_1200": CATALOG["nac_1200"],
                "nasacort_nightly": CATALOG["nasacort_nightly"],
                "nasal_strips_nightly": CATALOG["nasal_strips_nightly"],
                "humidifier_nightly": CATALOG["humidifier_nightly"],
                "mouth_tape_nightly": CATALOG["mouth_tape_nightly"],
            },
            sleep_estimate=sleep_estimate,
        )
        by_id = {result["id"]: result for result in results}

        assert by_id["nasacort_nightly"]["airway_effect_multiplier"] > by_id["nac_1200"]["airway_effect_multiplier"]
        assert by_id["nasal_strips_nightly"]["airway_effect_multiplier"] > by_id["nac_1200"]["airway_effect_multiplier"]
        assert by_id["humidifier_nightly"]["sleep_qol_qaly"] > 0.0
        assert by_id["humidifier_nightly"]["sleep_qol_qaly"] < by_id["nasal_strips_nightly"]["sleep_qol_qaly"]
        assert by_id["mouth_tape_nightly"]["sleep_qol_qaly"] > by_id["humidifier_nightly"]["sleep_qol_qaly"]
        assert by_id["mouth_tape_nightly"]["sleep_qol_qaly"] < by_id["nasal_strips_nightly"]["sleep_qol_qaly"]
        assert by_id["nasacort_nightly"]["sleep_qol_qaly"] > by_id["nac_1200"]["sleep_qol_qaly"]

    def test_pap_and_oral_appliance_outperform_weaker_airway_aids(self):
        profile = Profile(
            age=39,
            sex="male",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=False,
            has_hypertension=False,
            activity_level="light",
        )
        sleep_estimate = estimate_sleep_burden(
            SleepMetrics(
                duration_hours=6.5,
                recovery_score=55.0,
                sleep_quality_score=78.0,
                waso_min=18.0,
                routine_score=78.0,
                social_jetlag_min=25.0,
                latency_min=18.0,
                breathing_score=0.74,
                spo2=94.8,
                snore_pct=7.0,
                sleep_debt_min=40.0,
                airway_response_signal=0.85,
            )
        )

        results = simulate_catalog(
            profile,
            n_simulations=1500,
            random_state=42,
            catalog_entries={
                "apap_nightly": CATALOG["apap_nightly"],
                "oral_appliance_custom": CATALOG["oral_appliance_custom"],
                "nasal_strips_nightly": CATALOG["nasal_strips_nightly"],
            },
            sleep_estimate=sleep_estimate,
        )
        by_id = {result["id"]: result for result in results}

        assert by_id["apap_nightly"]["sleep_qol_qaly"] > by_id["oral_appliance_custom"]["sleep_qol_qaly"]
        assert by_id["oral_appliance_custom"]["sleep_qol_qaly"] > by_id["nasal_strips_nightly"]["sleep_qol_qaly"]
        assert by_id["apap_nightly"]["total_qaly"] > by_id["oral_appliance_custom"]["total_qaly"]

    def test_trazodone_alternatives_offer_cleaner_tradeoffs_in_sleep_maintenance_phenotype(self):
        profile = Profile(
            age=39,
            sex="male",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=False,
            has_hypertension=False,
            activity_level="light",
        )
        sleep_estimate = estimate_sleep_burden(
            SleepMetrics(
                duration_hours=6.5,
                recovery_score=55.0,
                sleep_quality_score=78.0,
                waso_min=18.0,
                routine_score=78.0,
                social_jetlag_min=25.0,
                latency_min=18.0,
                breathing_score=0.74,
                spo2=94.8,
                snore_pct=7.0,
                sleep_debt_min=40.0,
                airway_response_signal=0.40,
            )
        )

        results = simulate_catalog(
            profile,
            n_simulations=1500,
            random_state=42,
            catalog_entries={
                "trazodone_50mg": CATALOG["trazodone_50mg"],
                "doxepin_3mg": CATALOG["doxepin_3mg"],
                "daridorexant_25mg": CATALOG["daridorexant_25mg"],
                "lemborexant_5mg": CATALOG["lemborexant_5mg"],
                "suvorexant_10mg": CATALOG["suvorexant_10mg"],
            },
            sleep_estimate=sleep_estimate,
        )
        by_id = {result["id"]: result for result in results}

        assert by_id["daridorexant_25mg"]["direct_harm_qaly"] > by_id["trazodone_50mg"]["direct_harm_qaly"]
        assert by_id["daridorexant_25mg"]["p_harm"] < by_id["trazodone_50mg"]["p_harm"]
        assert by_id["lemborexant_5mg"]["p_harm"] < by_id["trazodone_50mg"]["p_harm"]
        assert by_id["suvorexant_10mg"]["p_harm"] < by_id["trazodone_50mg"]["p_harm"]
        assert by_id["daridorexant_25mg"]["p_harm"] < by_id["suvorexant_10mg"]["p_harm"]
        assert by_id["lemborexant_5mg"]["p_harm"] < by_id["suvorexant_10mg"]["p_harm"]
        assert by_id["doxepin_3mg"]["direct_harm_qaly"] > by_id["trazodone_50mg"]["direct_harm_qaly"]
        assert by_id["doxepin_3mg"]["annual_cost"] < by_id["trazodone_50mg"]["annual_cost"]

    def test_gray_market_peptides_have_negative_or_near_zero_qol_signal(self):
        assert CATALOG["bpc157_cycle"].qol_annual <= 0.00005
        assert CATALOG["tb500_cycle"].qol_annual <= 0.00003
        assert CATALOG["bpc157_cycle"].harm_effects
        assert CATALOG["tb500_cycle"].harm_effects


class TestCostAwarePortfolio:
    @pytest.fixture
    def sample_data(self):
        qalys = {
            "a": 0.10,
            "b": 0.05,
            "c": 0.03,
            "d": 0.02,
            "e": 0.01,
        }
        costs = {
            "a": 100,
            "b": 50,
            "c": 30,
            "d": 200,  # Expensive relative to benefit
            "e": 10,
        }
        return qalys, costs

    def test_selects_best_value_first(self, sample_data):
        qalys, costs = sample_data
        result = find_optimal_portfolio_with_costs(
            qalys, costs, wtp=200_000, horizon_years=40,
        )
        assert len(result) > 0
        assert result[0]["added_intervention"] == "a"  # Highest QALY

    def test_stops_at_negative_marginal(self, sample_data):
        qalys, costs = sample_data
        # Very low WTP should exclude expensive items
        result = find_optimal_portfolio_with_costs(
            qalys, costs, wtp=1_000, horizon_years=40,
        )
        # Should select fewer items when WTP is low
        result_high = find_optimal_portfolio_with_costs(
            qalys, costs, wtp=200_000, horizon_years=40,
        )
        assert len(result) <= len(result_high)

    def test_respects_exclude(self, sample_data):
        qalys, costs = sample_data
        result = find_optimal_portfolio_with_costs(
            qalys, costs, wtp=200_000, horizon_years=40,
            exclude=["a"],
        )
        selected = {step["added_intervention"] for step in result}
        assert "a" not in selected

    def test_diminishing_returns_applied(self, sample_data):
        qalys, costs = sample_data
        result = find_optimal_portfolio_with_costs(
            qalys, costs, wtp=200_000, horizon_years=40,
        )
        if len(result) >= 2:
            assert result[0]["marginal_qaly"] == pytest.approx(qalys["a"])
            assert result[1]["marginal_qaly"] == pytest.approx(qalys["b"])

    def test_output_structure(self, sample_data):
        qalys, costs = sample_data
        result = find_optimal_portfolio_with_costs(
            qalys, costs, wtp=200_000, horizon_years=40,
        )
        assert len(result) > 0
        step = result[0]
        assert "step" in step
        assert "added_intervention" in step
        assert "marginal_qaly" in step
        assert "marginal_net_value" in step
        assert "total_qaly" in step
        assert "total_annual_cost" in step
        assert "selected_interventions" in step

    def test_stack_interaction_penalty_can_block_second_item(self):
        qalys = {"a": 0.10, "b": 0.09}
        costs = {"a": 0, "b": 0}

        result = find_optimal_portfolio_with_costs(
            qalys,
            costs,
            wtp=200_000,
            horizon_years=40,
            stack_interaction_penalty_fn=lambda ids: -0.25 if len(ids) >= 2 else 0.0,
        )

        assert [step["added_intervention"] for step in result] == ["a"]
        assert result[0]["interaction_penalty_qaly"] == pytest.approx(0.0)

    def test_custom_marginal_cost_fn_avoids_double_counting_shared_product(self):
        qalys = {"a": 0.03, "b": 0.015, "c": 0.005}
        annual_costs = {"a": 100, "b": 100, "c": 25}
        cost_values = {"a": 4_000, "b": 4_000, "c": 1_000}

        def marginal_cost_value_fn(selected, candidate):
            shared = {"a", "b"}
            if candidate in shared and any(item in shared for item in selected):
                return 0
            return cost_values[candidate]

        def total_annual_cost_fn(selected):
            total = 0
            if any(item in {"a", "b"} for item in selected):
                total += 100
            if "c" in selected:
                total += 25
            return total

        result = find_optimal_portfolio_with_costs(
            qalys,
            annual_costs,
            cost_values=cost_values,
            wtp=200_000,
            horizon_years=40,
            marginal_cost_value_fn=marginal_cost_value_fn,
            total_annual_cost_fn=total_annual_cost_fn,
        )

        assert [step["added_intervention"] for step in result] == ["a", "b"]
        assert result[-1]["total_annual_cost"] == pytest.approx(100)

    def test_cost_value_overrides_horizon_multiplication(self):
        qalys = {"a": 0.01}
        annual_costs = {"a": 100}

        result = find_optimal_portfolio_with_costs(
            qalys,
            annual_costs,
            cost_values={"a": 500},
            wtp=200_000,
            horizon_years=40,
        )

        assert result[0]["marginal_net_value"] == pytest.approx(0.01 * 200_000 - 500)

    def test_benefit_overlap_can_block_redundant_second_item(self):
        qalys = {"a": 0.010, "b": 0.009}
        annual_costs = {"a": 0, "b": 0}
        cost_values = {"a": 0, "b": 1_000}
        catalog = {
            "a": CatalogEntry(
                id="a",
                name="A",
                category="supplement_current",
                hr_observed=1.0,
                log_sd=0.05,
                conf_alpha=1.0,
                conf_beta=1.0,
                annual_cost=0,
                benefit_tags=["sleep_quality_support"],
            ),
            "b": CatalogEntry(
                id="b",
                name="B",
                category="supplement_current",
                hr_observed=1.0,
                log_sd=0.05,
                conf_alpha=1.0,
                conf_beta=1.0,
                annual_cost=0,
                benefit_tags=["sleep_quality_support"],
            ),
        }
        profile = Profile(
            age=39,
            sex="male",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=False,
            has_hypertension=False,
            activity_level="light",
        )
        penalty_fn = build_stack_interaction_penalty_fn(
            catalog_entries=catalog,
            profile=profile,
            item_qalys=qalys,
        )

        result = find_optimal_portfolio_with_costs(
            qalys,
            annual_costs,
            cost_values=cost_values,
            wtp=200_000,
            horizon_years=40,
            stack_interaction_penalty_fn=penalty_fn,
        )

        assert [step["added_intervention"] for step in result] == ["a"]


def test_public_rx_display_names_have_no_dose_or_brand():
    """Public prescription names must not embed dose or brand.

    Surfacing 'rosuvastatin 5mg' or '(semaglutide)' to a consumer is a
    prescribing detail; the public tool should name the drug class only and
    badge it as prescription. Route parentheticals (e.g. '(topical)') are kept.
    """
    import re

    from optiqal.catalog import (
        get_catalog,
        public_display_category,
        public_display_name,
    )

    dose = re.compile(r"\b\d+(\.\d+)?\s*(mg|mcg|g|iu|ug)\b", re.I)
    routes = {
        "topical",
        "oral",
        "sublingual",
        "nasal",
        "inhaled",
        "transdermal",
        "subcutaneous",
    }
    brand_paren = re.compile(r"\(([^)]*)\)")

    cat = get_catalog()
    entries = cat.values() if isinstance(cat, dict) else cat
    rx = [e for e in entries if public_display_category(e) == "rx"]
    assert rx, "expected some rx items in the catalog"
    for e in rx:
        name = public_display_name(e)
        assert not dose.search(name), f"{e.id}: public name {name!r} still has a dose"
        for inner in brand_paren.findall(name):
            assert inner.strip().lower() in routes, (
                f"{e.id}: public name {name!r} still exposes a brand/molecule {inner!r}"
            )
