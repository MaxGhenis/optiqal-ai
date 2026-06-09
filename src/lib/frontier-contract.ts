import type {
  FrontierChoiceState,
  FrontierDecisionOption,
  FrontierDecisionOptionItem,
  FrontierDecisionSequenceStep,
  FrontierDecisionState,
  FrontierDecisionStateSummary,
  FrontierFrontierState,
  FrontierFrontierStateStep,
  FrontierItem,
  FrontierPublicPolicy,
  FrontierPublicPolicyCondition,
  FrontierPublicPolicyItem,
  FrontierPublicPolicyLane,
  FrontierRequest,
  FrontierResponse,
  FrontierSleepEstimate,
  FrontierStep,
} from "@/lib/frontier-types";
import {
  INVALID,
  isRecord,
  parseAccessLeaf,
  parseAnalysisProfileInput,
  parseAnalysisSleepInput,
  parseBoolean,
  parseFiniteNumber,
  parseMetaProfile,
  parseNumberRecord,
  parseOptionalArray,
  parseOptionalConfidenceInterval,
  parseOptionalFiniteNumber,
  parseOptionalBoundedNumber,
  parseString,
  parseStringArray,
} from "@/lib/contract-validation";

function parseNullableFiniteNumber(value: unknown): number | null | typeof INVALID {
  return value === null ? null : parseFiniteNumber(value) ?? INVALID;
}

function parseDecisionStateSummary(value: unknown): FrontierDecisionStateSummary | null {
  if (!isRecord(value)) {
    return null;
  }

  const itemIds = parseStringArray(value.item_ids);
  const baseQaly = parseFiniteNumber(value.base_qaly);
  const baseDays = parseFiniteNumber(value.base_days);
  const interactionPenaltyQaly = parseFiniteNumber(value.interaction_penalty_qaly);
  const adjustedQaly = parseFiniteNumber(value.adjusted_qaly);
  const adjustedDays = parseFiniteNumber(value.adjusted_days);
  const totalAnnualCost = parseFiniteNumber(value.total_annual_cost);

  if (
    itemIds === null ||
    baseQaly === null ||
    baseDays === null ||
    interactionPenaltyQaly === null ||
    adjustedQaly === null ||
    adjustedDays === null ||
    totalAnnualCost === null
  ) {
    return null;
  }

  return {
    item_ids: itemIds,
    base_qaly: baseQaly,
    base_days: baseDays,
    interaction_penalty_qaly: interactionPenaltyQaly,
    adjusted_qaly: adjustedQaly,
    adjusted_days: adjustedDays,
    total_annual_cost: totalAnnualCost,
  };
}

function parseDecisionOptionItem(value: unknown): FrontierDecisionOptionItem | null {
  if (!isRecord(value)) {
    return null;
  }

  const id = parseString(value.id);
  const name = parseString(value.name);
  const days = parseFiniteNumber(value.days);
  const annualCost = parseNullableFiniteNumber(value.annual_cost);
  const costPerQaly = parseNullableFiniteNumber(value.cost_per_qaly);
  const pBenefit = parseFiniteNumber(value.p_benefit);
  const pHarm = parseFiniteNumber(value.p_harm);
  const access = parseAccessProfile(value.access);

  if (
    id === null ||
    name === null ||
    days === null ||
    annualCost === INVALID ||
    costPerQaly === INVALID ||
    pBenefit === null ||
    pHarm === null ||
    access === null
  ) {
    return null;
  }

  return {
    id,
    name,
    days,
    annual_cost: annualCost,
    cost_per_qaly: costPerQaly,
    p_benefit: pBenefit,
    p_harm: pHarm,
    access,
  };
}

function parseDecisionOption(value: unknown): FrontierDecisionOption | null {
  if (!isRecord(value)) {
    return null;
  }

  const id = parseString(value.id);
  const label = parseString(value.label);
  const addedItemIds = parseStringArray(value.added_item_ids);
  const addedItems = parseOptionalArray(value.added_items, parseDecisionOptionItem);
  const marginalQaly = parseFiniteNumber(value.marginal_qaly);
  const marginalDays = parseFiniteNumber(value.marginal_days);
  const marginalAnnualCost = parseFiniteNumber(value.marginal_annual_cost);
  const marginalCostValue = parseFiniteNumber(value.marginal_cost_value);
  const marginalCostPerQaly = parseNullableFiniteNumber(value.marginal_cost_per_qaly);
  const stack = parseDecisionStateSummary(value.stack);
  const access = parseAccessProfile(value.access);

  if (
    id === null ||
    label === null ||
    addedItemIds === null ||
    addedItems === INVALID ||
    marginalQaly === null ||
    marginalDays === null ||
    marginalAnnualCost === null ||
    marginalCostValue === null ||
    marginalCostPerQaly === INVALID ||
    stack === null ||
    access === null
  ) {
    return null;
  }

  return {
    id,
    label,
    added_item_ids: addedItemIds,
    added_items: addedItems ?? [],
    marginal_qaly: marginalQaly,
    marginal_days: marginalDays,
    marginal_annual_cost: marginalAnnualCost,
    marginal_cost_value: marginalCostValue,
    marginal_cost_per_qaly: marginalCostPerQaly,
    stack,
    access,
  };
}

function parseFrontierStateStep(value: unknown): FrontierFrontierStateStep | null {
  if (!isRecord(value)) {
    return null;
  }

  const step = parseFiniteNumber(value.step);
  const id = parseString(value.id);
  const name = parseString(value.name);
  const marginalQaly = parseFiniteNumber(value.marginal_qaly);
  const marginalDays = parseFiniteNumber(value.marginal_days);
  const marginalCostPerQaly = parseNullableFiniteNumber(value.marginal_cost_per_qaly);
  const marginalInteractionDays = parseFiniteNumber(value.marginal_interaction_days);
  const cumulativeDays = parseFiniteNumber(value.cumulative_days);
  const totalAnnualCost = parseFiniteNumber(value.total_annual_cost);

  if (
    step === null ||
    id === null ||
    name === null ||
    marginalQaly === null ||
    marginalDays === null ||
    marginalCostPerQaly === INVALID ||
    marginalInteractionDays === null ||
    cumulativeDays === null ||
    totalAnnualCost === null
  ) {
    return null;
  }

  return {
    step,
    id,
    name,
    marginal_qaly: marginalQaly,
    marginal_days: marginalDays,
    marginal_cost_per_qaly: marginalCostPerQaly,
    marginal_interaction_days: marginalInteractionDays,
    cumulative_days: cumulativeDays,
    total_annual_cost: totalAnnualCost,
  };
}

function parseDecisionState(value: unknown): FrontierDecisionState | null {
  if (!isRecord(value)) {
    return null;
  }

  const kind = parseString(value.kind);
  const id = parseString(value.id);
  const label = parseString(value.label);
  const description = parseString(value.description);
  const baseline = parseDecisionStateSummary(value.baseline);

  if (
    kind === null ||
    id === null ||
    label === null ||
    description === null ||
    baseline === null
  ) {
    return null;
  }

  if (kind === "choice") {
    const bestBiologyOptionId =
      value.best_biology_option_id === null
        ? null
        : parseString(value.best_biology_option_id);
    const bestAccessOptionId =
      value.best_access_option_id === null
        ? null
        : parseString(value.best_access_option_id);
    const options = parseOptionalArray(value.options, parseDecisionOption);

    if (
      bestBiologyOptionId === null && value.best_biology_option_id !== null ||
      bestAccessOptionId === null && value.best_access_option_id !== null ||
      options === INVALID
    ) {
      return null;
    }

    return {
      id,
      kind,
      label,
      description,
      baseline,
      best_biology_option_id: bestBiologyOptionId,
      best_access_option_id: bestAccessOptionId,
      options: options ?? [],
    } satisfies FrontierChoiceState;
  }

  if (kind === "frontier") {
    const steps = parseOptionalArray(value.steps, parseFrontierStateStep);
    if (steps === INVALID) {
      return null;
    }

    return {
      id,
      kind,
      label,
      description,
      baseline,
      steps: steps ?? [],
    } satisfies FrontierFrontierState;
  }

  return null;
}

function parseDecisionSequenceStep(value: unknown): FrontierDecisionSequenceStep | null {
  if (!isRecord(value)) {
    return null;
  }

  const step = parseFiniteNumber(value.step);
  const id = parseString(value.id);
  const label = parseString(value.label);
  const stateId = value.state_id === undefined ? undefined : parseString(value.state_id);
  const preferredStateId =
    value.preferred_state_id === undefined
      ? undefined
      : parseString(value.preferred_state_id);
  const alternativeStateId =
    value.alternative_state_id === undefined
      ? undefined
      : parseString(value.alternative_state_id);

  if (
    step === null ||
    id === null ||
    label === null ||
    (value.state_id !== undefined && stateId === null) ||
    (value.preferred_state_id !== undefined && preferredStateId === null) ||
    (value.alternative_state_id !== undefined && alternativeStateId === null)
  ) {
    return null;
  }

  const parsedStep: FrontierDecisionSequenceStep = {
    step,
    id,
    label,
  };
  if (stateId !== undefined && stateId !== null) {
    parsedStep.state_id = stateId;
  }
  if (preferredStateId !== undefined && preferredStateId !== null) {
    parsedStep.preferred_state_id = preferredStateId;
  }
  if (alternativeStateId !== undefined && alternativeStateId !== null) {
    parsedStep.alternative_state_id = alternativeStateId;
  }
  return parsedStep;
}

function parseAccessProfile(value: unknown): FrontierItem["access"] | null {
  if (!isRecord(value)) {
    return null;
  }

  const leaf = parseAccessLeaf(value);
  const itemAccesses = parseOptionalArray(value.item_accesses, parseAccessLeaf);
  if (leaf === null || itemAccesses === INVALID) {
    return null;
  }

  return {
    ...leaf,
    ...(itemAccesses !== undefined ? { item_accesses: itemAccesses } : {}),
  };
}

function parseFrontierItem(value: unknown): FrontierItem | null {
  if (!isRecord(value)) {
    return null;
  }

  const id = parseString(value.id);
  const name = parseString(value.name);
  const category = parseString(value.category);
  const displayCategory = parseString(value.display_category);
  const publicLane = parseString(value.public_lane);
  const annualCost = parseNullableFiniteNumber(value.annual_cost);
  const totalCost = parseFiniteNumber(value.total_cost);
  const costPerQaly = parseNullableFiniteNumber(value.cost_per_qaly);
  const totalQaly = parseFiniteNumber(value.total_qaly);
  const netQalyCi = parseOptionalConfidenceInterval(value.net_qaly_ci);
  const netDaysCi = parseOptionalConfidenceInterval(value.net_days_ci);
  const days = parseFiniteNumber(value.days);
  const pBenefit = parseFiniteNumber(value.p_benefit);
  const pHarm = parseFiniteNumber(value.p_harm);
  const mortQaly = parseFiniteNumber(value.mort_qaly);
  const harmQaly = parseFiniteNumber(value.harm_qaly);
  const qolQaly = parseFiniteNumber(value.qol_qaly);
  const sleepQolQaly = parseFiniteNumber(value.sleep_qol_qaly);
  const profileEffectMultiplier = parseFiniteNumber(value.profile_effect_multiplier);
  const airwayEffectMultiplier = parseFiniteNumber(value.airway_effect_multiplier);
  const sleepMortalityHrMultiplier = parseFiniteNumber(value.sleep_mortality_hr_multiplier);
  const sleepMortalityReliefFraction = parseFiniteNumber(value.sleep_mortality_relief_fraction);
  const interactionTags = parseStringArray(value.interaction_tags);
  const benefitTags = parseStringArray(value.benefit_tags);
  const notes = parseString(value.notes);
  const sources = parseStringArray(value.sources);
  const selectedInFrontier = parseBoolean(value.selected_in_frontier);
  const pricingStatus = parseString(value.pricing_status);
  const rankabilityReason =
    value.rankability_reason === null ? null : parseString(value.rankability_reason);
  const access = parseAccessProfile(value.access);

  if (
    id === null ||
    name === null ||
    category === null ||
    displayCategory === null ||
    (
      publicLane !== "consumer_public" &&
      publicLane !== "conditional_public" &&
      publicLane !== "personal_only"
    ) ||
    annualCost === INVALID ||
    totalCost === null ||
    costPerQaly === INVALID ||
    totalQaly === null ||
    netQalyCi === INVALID ||
    netDaysCi === INVALID ||
    days === null ||
    pBenefit === null ||
    pHarm === null ||
    mortQaly === null ||
    harmQaly === null ||
    qolQaly === null ||
    sleepQolQaly === null ||
    profileEffectMultiplier === null ||
    airwayEffectMultiplier === null ||
    sleepMortalityHrMultiplier === null ||
    sleepMortalityReliefFraction === null ||
    interactionTags === null ||
    benefitTags === null ||
    notes === null ||
    sources === null ||
    selectedInFrontier === null ||
    (pricingStatus !== "priced" && pricingStatus !== "free" && pricingStatus !== "unpriced") ||
    (value.rankability_reason !== null && rankabilityReason === null) ||
    access === null
  ) {
    return null;
  }

  return {
    id,
    name,
    category,
    display_category: displayCategory,
    public_lane: publicLane,
    annual_cost: annualCost,
    total_cost: totalCost,
    cost_per_qaly: costPerQaly,
    total_qaly: totalQaly,
    ...(netQalyCi !== undefined ? { net_qaly_ci: netQalyCi } : {}),
    ...(netDaysCi !== undefined ? { net_days_ci: netDaysCi } : {}),
    days,
    p_benefit: pBenefit,
    p_harm: pHarm,
    mort_qaly: mortQaly,
    harm_qaly: harmQaly,
    qol_qaly: qolQaly,
    sleep_qol_qaly: sleepQolQaly,
    profile_effect_multiplier: profileEffectMultiplier,
    airway_effect_multiplier: airwayEffectMultiplier,
    sleep_mortality_hr_multiplier: sleepMortalityHrMultiplier,
    sleep_mortality_relief_fraction: sleepMortalityReliefFraction,
    interaction_tags: interactionTags,
    benefit_tags: benefitTags,
    notes,
    sources,
    selected_in_frontier: selectedInFrontier,
    pricing_status: pricingStatus,
    rankability_reason: rankabilityReason,
    access,
  };
}

function parseFrontierStep(value: unknown): FrontierStep | null {
  if (!isRecord(value)) {
    return null;
  }

  const step = parseFiniteNumber(value.step);
  const addedIntervention = parseString(value.added_intervention);
  const addedName = parseString(value.added_name);
  const marginalQaly = parseFiniteNumber(value.marginal_qaly);
  const marginalDays = parseFiniteNumber(value.marginal_days);
  const marginalCostPerQaly = parseNullableFiniteNumber(value.marginal_cost_per_qaly);
  const marginalCostValue = parseFiniteNumber(value.marginal_cost_value);
  const marginalInteractionQaly = parseFiniteNumber(value.marginal_interaction_qaly);
  const totalQaly = parseFiniteNumber(value.total_qaly);
  const totalDays = parseFiniteNumber(value.total_days);
  const interactionPenaltyQaly = parseFiniteNumber(value.interaction_penalty_qaly);
  const interactionPenaltyDays = parseFiniteNumber(value.interaction_penalty_days);
  const totalCostValue = parseFiniteNumber(value.total_cost_value);
  const totalAnnualCost = parseFiniteNumber(value.total_annual_cost);
  const selectedInterventions = parseStringArray(value.selected_interventions);

  if (
    step === null ||
    addedIntervention === null ||
    addedName === null ||
    marginalQaly === null ||
    marginalDays === null ||
    marginalCostPerQaly === INVALID ||
    marginalCostValue === null ||
    marginalInteractionQaly === null ||
    totalQaly === null ||
    totalDays === null ||
    interactionPenaltyQaly === null ||
    interactionPenaltyDays === null ||
    totalCostValue === null ||
    totalAnnualCost === null ||
    selectedInterventions === null
  ) {
    return null;
  }

  return {
    step,
    added_intervention: addedIntervention,
    added_name: addedName,
    marginal_qaly: marginalQaly,
    marginal_days: marginalDays,
    marginal_cost_per_qaly: marginalCostPerQaly,
    marginal_cost_value: marginalCostValue,
    marginal_interaction_qaly: marginalInteractionQaly,
    total_qaly: totalQaly,
    total_days: totalDays,
    interaction_penalty_qaly: interactionPenaltyQaly,
    interaction_penalty_days: interactionPenaltyDays,
    total_cost_value: totalCostValue,
    total_annual_cost: totalAnnualCost,
    selected_interventions: selectedInterventions,
  };
}

function parseSleepEstimate(value: unknown): FrontierSleepEstimate | null {
  if (value === null) {
    return null;
  }
  if (!isRecord(value)) {
    return null;
  }

  const annualQalyLoss = parseFiniteNumber(value.annual_qaly_loss);
  const mortalitySignal = parseFiniteNumber(value.mortality_signal);
  const componentLosses = parseNumberRecord(value.component_losses);
  const componentBurdens = parseNumberRecord(value.component_burdens);

  let airway: FrontierSleepEstimate["airway"] = null;
  if (value.airway !== null && value.airway !== undefined) {
    if (!isRecord(value.airway)) {
      return null;
    }

    const upperAirwayProbability = parseFiniteNumber(value.airway.upper_airway_probability);
    const nasalInflammationProbability = parseFiniteNumber(
      value.airway.nasal_inflammation_probability
    );
    const mucusProbability = parseFiniteNumber(value.airway.mucus_probability);
    const responseSignal = parseFiniteNumber(value.airway.response_signal);

    if (
      upperAirwayProbability === null ||
      nasalInflammationProbability === null ||
      mucusProbability === null ||
      responseSignal === null
    ) {
      return null;
    }

    airway = {
      upper_airway_probability: upperAirwayProbability,
      nasal_inflammation_probability: nasalInflammationProbability,
      mucus_probability: mucusProbability,
      response_signal: responseSignal,
    };
  }

  if (
    annualQalyLoss === null ||
    mortalitySignal === null ||
    componentLosses === null ||
    componentBurdens === null
  ) {
    return null;
  }

  return {
    annual_qaly_loss: annualQalyLoss,
    mortality_signal: mortalitySignal,
    component_losses: componentLosses,
    component_burdens: componentBurdens,
    airway,
  };
}

function parsePublicPolicyLane(value: unknown): FrontierPublicPolicyLane | null {
  if (!isRecord(value)) {
    return null;
  }

  const id = parseString(value.id);
  const label = parseString(value.label);
  const description = parseString(value.description);
  const itemIds = parseStringArray(value.item_ids);
  const itemCount = parseFiniteNumber(value.item_count);
  const conditionIds = parseStringArray(value.condition_ids);

  if (
    (id !== "consumer_public" && id !== "conditional_public" && id !== "personal_only") ||
    label === null ||
    description === null ||
    itemIds === null ||
    itemCount === null ||
    conditionIds === null
  ) {
    return null;
  }

  return {
    id,
    label,
    description,
    item_ids: itemIds,
    item_count: itemCount,
    condition_ids: conditionIds,
  };
}

function parsePublicPolicyCondition(value: unknown): FrontierPublicPolicyCondition | null {
  if (!isRecord(value)) {
    return null;
  }

  const id = parseString(value.id);
  const label = parseString(value.label);
  const description = parseString(value.description);
  const itemIds = parseStringArray(value.item_ids);
  const itemCount = parseFiniteNumber(value.item_count);
  const evaluationKind = parseString(value.evaluation_kind);
  const hasScoreThreshold = "score_threshold" in value;
  const scoreThreshold = value.score_threshold === null ? null : parseFiniteNumber(value.score_threshold);
  const thresholds = parseOptionalArray(value.thresholds, (rule) => {
    if (!isRecord(rule)) {
      return null;
    }

    const signal = parseString(rule.signal);
    const thresholdLabel = parseString(rule.label);
    const thresholdValue = parseFiniteNumber(rule.threshold);

    if (signal === null || thresholdLabel === null || thresholdValue === null) {
      return null;
    }

    return {
      signal,
      label: thresholdLabel,
      threshold: thresholdValue,
    };
  });
  const scoreRules = parseOptionalArray(value.score_rules, (rule) => {
    if (!isRecord(rule)) {
      return null;
    }

    const field = parseString(rule.field);
    const operator = parseString(rule.operator);
    const scoreLabel = parseString(rule.label);
    const points = parseFiniteNumber(rule.points);

    if (
      field === null ||
      (operator !== "gte" && operator !== "eq" && operator !== "in") ||
      scoreLabel === null ||
      points === null
    ) {
      return null;
    }

    return {
      field,
      operator: operator as "gte" | "eq" | "in",
      label: scoreLabel,
      points,
    };
  });

  if (
    (
      id !== "airway_signal" &&
      id !== "cardiometabolic_signal" &&
      id !== "metabolic_signal" &&
      id !== "glp1_signal" &&
      id !== "nasal_dryness_signal" &&
      id !== "osa_therapy_signal"
    ) ||
    label === null ||
    description === null ||
    itemIds === null ||
    itemCount === null ||
    (evaluationKind !== "sleep_any_threshold" && evaluationKind !== "profile_score") ||
    !hasScoreThreshold ||
    (value.score_threshold !== null && scoreThreshold === null) ||
    thresholds === INVALID ||
    scoreRules === INVALID
  ) {
    return null;
  }

  return {
    id,
    label,
    description,
    item_ids: itemIds,
    item_count: itemCount,
    evaluation_kind: evaluationKind,
    score_threshold: scoreThreshold,
    thresholds: thresholds ?? [],
    score_rules: scoreRules ?? [],
  };
}

function parsePublicPolicyItem(value: unknown): FrontierPublicPolicyItem | null {
  if (!isRecord(value)) {
    return null;
  }

  const id = parseString(value.id);
  const name = parseString(value.name);
  const lane = parseString(value.lane);
  const conditionRaw = value.condition === null ? null : parseString(value.condition);
  const displayCategory = parseString(value.display_category);
  const explicitlyExcluded = parseBoolean(value.explicitly_excluded);

  let condition: FrontierPublicPolicyItem["condition"] = null;
  if (conditionRaw !== null) {
    if (
      conditionRaw !== "airway_signal" &&
      conditionRaw !== "cardiometabolic_signal" &&
      conditionRaw !== "metabolic_signal" &&
      conditionRaw !== "glp1_signal" &&
      conditionRaw !== "nasal_dryness_signal" &&
      conditionRaw !== "osa_therapy_signal"
    ) {
      return null;
    }
    condition = conditionRaw;
  }

  if (
    id === null ||
    name === null ||
    (lane !== "consumer_public" && lane !== "conditional_public" && lane !== "personal_only") ||
    displayCategory === null ||
    explicitlyExcluded === null
  ) {
    return null;
  }

  return {
    id,
    name,
    lane,
    condition,
    display_category: displayCategory,
    explicitly_excluded: explicitlyExcluded,
  };
}

function parsePublicPolicy(value: unknown): FrontierPublicPolicy | null {
  if (!isRecord(value)) {
    return null;
  }

  const lanes = parseOptionalArray(value.lanes, parsePublicPolicyLane);
  const conditions = parseOptionalArray(value.conditions, parsePublicPolicyCondition);
  const items = parseOptionalArray(value.items, parsePublicPolicyItem);

  if (lanes === INVALID || conditions === INVALID || items === INVALID) {
    return null;
  }

  return {
    lanes: lanes ?? [],
    conditions: conditions ?? [],
    items: items ?? [],
  };
}

export function parseFrontierRequest(value: unknown): FrontierRequest | null {
  if (!isRecord(value)) {
    return null;
  }

  const profile = parseAnalysisProfileInput(value.profile);
  const sleepMetrics = parseAnalysisSleepInput(value.sleep_metrics);
  // Bound simulation count: an unbounded value lets a single request make the
  // engine allocate/iterate arbitrarily large arrays (CPU/memory exhaustion).
  const nSimulations = parseOptionalBoundedNumber(value.n_simulations, 1, 20000);

  if (profile === null || sleepMetrics === INVALID || nSimulations === INVALID) {
    return null;
  }

  return {
    profile,
    ...(sleepMetrics !== undefined ? { sleep_metrics: sleepMetrics } : {}),
    ...(typeof nSimulations === "number" ? { n_simulations: nSimulations } : {}),
  };
}

export function parseFrontierResponse(value: unknown): FrontierResponse | null {
  if (!isRecord(value) || !isRecord(value.meta)) {
    return null;
  }

  const selectionMode = parseString(value.meta.selection_mode);
  const analyzedCount = parseFiniteNumber(value.meta.analyzed_count);
  const positiveCount = parseFiniteNumber(value.meta.positive_count);
  const qalyDiscountRate = parseFiniteNumber(value.meta.qaly_discount_rate);
  const costDiscountRate = parseFiniteNumber(value.meta.cost_discount_rate);
  const nSimulations = parseFiniteNumber(value.meta.n_simulations);
  const rankableCount = parseFiniteNumber(value.meta.rankable_count);
  const profile = parseMetaProfile(value.meta.profile);
  const sleepEstimate = parseSleepEstimate(value.sleep_estimate);
  const publicPolicy = parsePublicPolicy(value.public_policy);
  const frontier = parseOptionalArray(value.frontier, parseFrontierStep);
  const items = parseOptionalArray(value.items, parseFrontierItem);
  const decisionStates = parseOptionalArray(value.decision_states, parseDecisionState);
  const decisionSequence = parseOptionalArray(value.decision_sequence, parseDecisionSequenceStep);

  if (
    selectionMode === null ||
    analyzedCount === null ||
    positiveCount === null ||
    qalyDiscountRate === null ||
    costDiscountRate === null ||
    nSimulations === null ||
    rankableCount === null ||
    profile === null ||
    (value.sleep_estimate !== null && sleepEstimate === null) ||
    publicPolicy === null ||
    frontier === INVALID ||
    items === INVALID ||
    decisionStates === INVALID ||
    decisionSequence === INVALID
  ) {
    return null;
  }

  return {
    meta: {
      selection_mode: selectionMode,
      analyzed_count: analyzedCount,
      positive_count: positiveCount,
      qaly_discount_rate: qalyDiscountRate,
      cost_discount_rate: costDiscountRate,
      n_simulations: nSimulations,
      rankable_count: rankableCount,
      profile,
    },
    sleep_estimate: sleepEstimate,
    public_policy: publicPolicy,
    frontier: frontier ?? [],
    items: items ?? [],
    decision_states: decisionStates ?? [],
    decision_sequence: decisionSequence ?? [],
  };
}
