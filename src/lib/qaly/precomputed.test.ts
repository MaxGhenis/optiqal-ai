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
      expect(matchIntervention("do laughter therapy")).toBeNull();
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
