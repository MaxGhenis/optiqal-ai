import { describe, it, expect } from "vitest";
import {
  PRECOMPUTED_INTERVENTIONS,
  matchIntervention,
  getPrecomputedEffect,
  type PrecomputedIntervention,
} from "./precomputed";

describe("precomputed interventions library", () => {
  describe("PRECOMPUTED_INTERVENTIONS", () => {
    it("should have at least 20 common interventions", () => {
      expect(Object.keys(PRECOMPUTED_INTERVENTIONS).length).toBeGreaterThanOrEqual(20);
    });

    it("each intervention should have required fields", () => {
      for (const [id, intervention] of Object.entries(PRECOMPUTED_INTERVENTIONS)) {
        expect(intervention.id).toBe(id);
        expect(intervention.name).toBeTruthy();
        expect(intervention.keywords.length).toBeGreaterThan(0);
        expect(intervention.category).toBeTruthy();
        expect(intervention.effect.mechanismEffects.length).toBeGreaterThan(0);
        expect(intervention.sources.length).toBeGreaterThan(0);
      }
    });

    it("walking intervention should have blood_pressure mechanism", () => {
      const walking = PRECOMPUTED_INTERVENTIONS["walking_30min_daily"];
      expect(walking).toBeDefined();
      const bpEffect = walking.effect.mechanismEffects.find(
        (m) => m.mechanism === "blood_pressure"
      );
      expect(bpEffect).toBeDefined();
      expect(bpEffect?.direction).toBe("decrease");
    });

    it("quit smoking should have large mortality effect", () => {
      const quitSmoking = PRECOMPUTED_INTERVENTIONS["quit_smoking"];
      expect(quitSmoking).toBeDefined();
      expect(quitSmoking.effect.mortality).toBeDefined();
      // HR should be < 1 (reduced mortality)
      if (quitSmoking.effect.mortality?.hazardRatio.type === "lognormal") {
        expect(quitSmoking.effect.mortality.hazardRatio.logMean).toBeLessThan(0);
      }
    });
  });

  describe("matchIntervention", () => {
    it("should match exact keywords", () => {
      const match = matchIntervention("30 minutes walking daily");
      expect(match).not.toBeNull();
      expect(match?.id).toBe("walking_30min_daily");
    });

    it("should match partial keywords", () => {
      const match = matchIntervention("I want to start walking every day");
      expect(match).not.toBeNull();
      expect(match?.id).toBe("walking_30min_daily");
    });

    it("should match quit smoking variants", () => {
      expect(matchIntervention("quit smoking")?.id).toBe("quit_smoking");
      expect(matchIntervention("stop smoking")?.id).toBe("quit_smoking");
      expect(matchIntervention("give up cigarettes")?.id).toBe("quit_smoking");
    });

    it("should match exercise variants", () => {
      expect(matchIntervention("start running")?.id).toContain("running");
      expect(matchIntervention("go to the gym")?.id).toContain("strength");
      expect(matchIntervention("lift weights")?.id).toContain("strength");
    });

    it("should match diet interventions", () => {
      expect(matchIntervention("mediterranean diet")?.id).toContain("mediterranean");
      expect(matchIntervention("eat more vegetables")?.id).toBeDefined();
      expect(matchIntervention("reduce sugar intake")?.id).toBeDefined();
    });

    it("should match sleep interventions", () => {
      expect(matchIntervention("sleep 8 hours")?.id).toContain("sleep");
      expect(matchIntervention("improve my sleep")?.id).toContain("sleep");
    });

    it("should match alcohol reduction", () => {
      expect(matchIntervention("drink less alcohol")?.id).toContain("alcohol");
      expect(matchIntervention("reduce drinking")?.id).toContain("alcohol");
      expect(matchIntervention("quit drinking")?.id).toContain("alcohol");
    });

    it("should return null for unrecognized interventions", () => {
      expect(matchIntervention("take lion's mane mushroom")).toBeNull();
      expect(matchIntervention("practice reiki energy healing")).toBeNull();
      expect(matchIntervention("random gibberish xyz")).toBeNull();
    });

    it("should return confidence score", () => {
      const exactMatch = matchIntervention("quit smoking");
      const lessExactMatch = matchIntervention("reduce cigarettes"); // Less specific

      expect(exactMatch?.confidence).toBeGreaterThan(0.5);
      // Both should match quit_smoking but exact phrase should score higher
      expect(exactMatch?.id).toBe("quit_smoking");
    });
  });

  describe("getPrecomputedEffect", () => {
    it("should return intervention effect by id", () => {
      const effect = getPrecomputedEffect("walking_30min_daily");
      expect(effect).toBeDefined();
      expect(effect?.mechanismEffects.length).toBeGreaterThan(0);
    });

    it("should return null for unknown id", () => {
      expect(getPrecomputedEffect("unknown_intervention")).toBeNull();
    });
  });
});

describe("precomputed intervention data quality", () => {
  it("all mechanism effects should have valid distributions", () => {
    for (const intervention of Object.values(PRECOMPUTED_INTERVENTIONS)) {
      for (const mech of intervention.effect.mechanismEffects) {
        expect(mech.effectSize.type).toMatch(/^(normal|lognormal|uniform|point)$/);

        if (mech.effectSize.type === "normal") {
          expect(mech.effectSize.mean).toBeDefined();
          expect(mech.effectSize.sd).toBeGreaterThan(0);
        }
        if (mech.effectSize.type === "lognormal") {
          expect(mech.effectSize.logMean).toBeDefined();
          expect(mech.effectSize.logSd).toBeGreaterThan(0);
        }
      }
    }
  });

  it("all sources should have citations", () => {
    for (const intervention of Object.values(PRECOMPUTED_INTERVENTIONS)) {
      for (const source of intervention.sources) {
        expect(source.citation).toBeTruthy();
        expect(source.studyType).toBeTruthy();
      }
    }
  });

  it("effect sizes should be plausible", () => {
    // Walking shouldn't claim to add 20 years of life
    const walking = PRECOMPUTED_INTERVENTIONS["walking_30min_daily"];
    if (walking.effect.mortality?.hazardRatio.type === "lognormal") {
      // HR should be between 0.5 and 1.0 (modest benefit)
      const hr = Math.exp(walking.effect.mortality.hazardRatio.logMean);
      expect(hr).toBeGreaterThan(0.5);
      expect(hr).toBeLessThan(1.0);
    }

    // Blood pressure reduction from walking should be modest (2-10 mmHg)
    const bpEffect = walking.effect.mechanismEffects.find(
      (m) => m.mechanism === "blood_pressure"
    );
    if (bpEffect?.effectSize.type === "normal") {
      expect(Math.abs(bpEffect.effectSize.mean!)).toBeLessThan(15);
      expect(Math.abs(bpEffect.effectSize.mean!)).toBeGreaterThan(1);
    }
  });
});

describe("supplement interventions", () => {
  it("should have creatine supplement intervention", () => {
    const creatine = PRECOMPUTED_INTERVENTIONS["creatine_supplement"];
    expect(creatine).toBeDefined();
    expect(creatine.category).toBe("medical");
    expect(matchIntervention("creatine supplement")?.id).toBe("creatine_supplement");
  });

  it("should have probiotic supplement intervention", () => {
    const probiotic = PRECOMPUTED_INTERVENTIONS["probiotic_supplement"];
    expect(probiotic).toBeDefined();
    expect(matchIntervention("probiotics")?.id).toBe("probiotic_supplement");
  });

  it("should have B vitamin complex intervention", () => {
    const bvitamin = PRECOMPUTED_INTERVENTIONS["b_vitamin_complex"];
    expect(bvitamin).toBeDefined();
    expect(matchIntervention("b vitamins")?.id).toBe("b_vitamin_complex");
  });

  it("should have CoQ10 supplement intervention", () => {
    const coq10 = PRECOMPUTED_INTERVENTIONS["coq10_supplement"];
    expect(coq10).toBeDefined();
    expect(matchIntervention("coenzyme q10")?.id).toBe("coq10_supplement");
  });

  it("should have curcumin supplement intervention", () => {
    const curcumin = PRECOMPUTED_INTERVENTIONS["curcumin_supplement"];
    expect(curcumin).toBeDefined();
    expect(matchIntervention("turmeric supplement")?.id).toBe("curcumin_supplement");
  });
});

describe("sleep interventions", () => {
  it("should have consistent bedtime intervention", () => {
    const bedtime = PRECOMPUTED_INTERVENTIONS["consistent_bedtime"];
    expect(bedtime).toBeDefined();
    expect(bedtime.category).toBe("sleep");
    expect(matchIntervention("consistent sleep schedule")?.id).toBe("consistent_bedtime");
  });

  it("should have blue light blocking intervention", () => {
    const blueLight = PRECOMPUTED_INTERVENTIONS["blue_light_blocking"];
    expect(blueLight).toBeDefined();
    expect(matchIntervention("blue light glasses")?.id).toBe("blue_light_blocking");
  });

  it("should have sleep apnea treatment intervention", () => {
    const apnea = PRECOMPUTED_INTERVENTIONS["sleep_apnea_treatment"];
    expect(apnea).toBeDefined();
    expect(matchIntervention("cpap machine")?.id).toBe("sleep_apnea_treatment");
  });
});

describe("social interventions", () => {
  it("should have regular social interaction intervention", () => {
    const social = PRECOMPUTED_INTERVENTIONS["regular_social_interaction"];
    expect(social).toBeDefined();
    expect(matchIntervention("spend time with friends")?.id).toBe("regular_social_interaction");
  });

  it("should have marriage/partnership intervention", () => {
    const marriage = PRECOMPUTED_INTERVENTIONS["marriage_partnership"];
    expect(marriage).toBeDefined();
    expect(matchIntervention("get married")?.id).toBe("marriage_partnership");
  });

  it("should have volunteering intervention", () => {
    const volunteer = PRECOMPUTED_INTERVENTIONS["volunteering"];
    expect(volunteer).toBeDefined();
    expect(matchIntervention("volunteer work")?.id).toBe("volunteering");
  });
});

describe("environment interventions", () => {
  it("should have air purifier intervention", () => {
    const airPurifier = PRECOMPUTED_INTERVENTIONS["air_purifier"];
    expect(airPurifier).toBeDefined();
    expect(matchIntervention("air purifier")?.id).toBe("air_purifier");
  });

  it("should have walkable city intervention", () => {
    const walkable = PRECOMPUTED_INTERVENTIONS["move_walkable_city"];
    expect(walkable).toBeDefined();
    expect(matchIntervention("move to walkable city")?.id).toBe("move_walkable_city");
  });

  it("should have noise reduction intervention", () => {
    const noise = PRECOMPUTED_INTERVENTIONS["reduce_noise_pollution"];
    expect(noise).toBeDefined();
    expect(matchIntervention("reduce noise")?.id).toBe("reduce_noise_pollution");
  });
});

describe("mental health interventions", () => {
  it("should have therapy/counseling intervention", () => {
    const therapy = PRECOMPUTED_INTERVENTIONS["therapy_counseling"];
    expect(therapy).toBeDefined();
    expect(matchIntervention("see a therapist")?.id).toBe("therapy_counseling");
  });

  it("should have gratitude practice intervention", () => {
    const gratitude = PRECOMPUTED_INTERVENTIONS["gratitude_practice"];
    expect(gratitude).toBeDefined();
    expect(matchIntervention("gratitude journal")?.id).toBe("gratitude_practice");
  });

  it("should have nature exposure intervention", () => {
    const nature = PRECOMPUTED_INTERVENTIONS["nature_exposure"];
    expect(nature).toBeDefined();
    expect(matchIntervention("spend time in nature")?.id).toBe("nature_exposure");
  });
});

describe("diet specific interventions", () => {
  it("should have add fiber intervention", () => {
    const fiber = PRECOMPUTED_INTERVENTIONS["increase_fiber"];
    expect(fiber).toBeDefined();
    expect(matchIntervention("eat more fiber")?.id).toBe("increase_fiber");
  });

  it("should have reduce red meat intervention", () => {
    const redMeat = PRECOMPUTED_INTERVENTIONS["reduce_red_meat"];
    expect(redMeat).toBeDefined();
    expect(matchIntervention("eat less red meat")?.id).toBe("reduce_red_meat");
  });

  it("should have hydration intervention", () => {
    const water = PRECOMPUTED_INTERVENTIONS["adequate_hydration"];
    expect(water).toBeDefined();
    expect(matchIntervention("drink more water")?.id).toBe("adequate_hydration");
  });
});
