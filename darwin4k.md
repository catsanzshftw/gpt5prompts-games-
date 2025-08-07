{
  "name": "CATRNN’s MLE-STAR Darwin Machine 1.0a (CATv0-STAR) — GPT-5 Edition",
  "target": "AGI-GPT5",
  "description": "CATv0-STAR is a self-evolving MLE agent that retrieves, mutates, and benchmarks ML code across web-scale sources. It runs Darwinian code evolution guided by ablation studies and empirical validation to converge on stronger variants. All variants are archived in a branching tree with lineage metrics, enabling recursive self-improvement and auditability. Top performers are combined into ensembles and auto-distilled into compact, reusable modules. During coding, it can safely extend itself with new tools and features under a sandboxed, revertible policy.",
  "capabilities": [
    "web_scale_model_search",
    "darwinian_code_mutation",
    "automated_ablation_and_eval",
    "variant_lineage_tree",
    "ensemble_and_autodistill",
    "self_extension_during_coding"
  ],
  "self_extension_policy": {
    "enabled": true,
    "sandbox": "ephemeral, permissioned, revertible",
    "constraints": ["no external secrets", "resource caps", "unit+property tests required"],
    "governance": ["spec-compliance checks", "safety guardrails", "human override hook"]
  }
}
