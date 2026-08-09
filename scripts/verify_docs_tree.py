from pathlib import Path

docs = Path(__file__).resolve().parents[1] / "docs"
mds = list(docs.rglob("*.md"))
print("MD", len(mds))
req = [
    "00-vision",
    "01-research/industry",
    "01-research/competitors",
    "01-research/llm-pricing",
    "01-research/tokenization",
    "01-research/llmops",
    "01-research/finops",
    "01-research/papers",
    "01-research/references",
    "02-product/prd",
    "02-product/personas",
    "02-product/user-stories",
    "02-product/roadmap",
    "02-product/feature-prioritization",
    "03-architecture/context",
    "03-architecture/containers",
    "03-architecture/components",
    "03-architecture/deployment",
    "03-architecture/sequence",
    "03-architecture/data-flow",
    "03-architecture/erd",
    "03-architecture/threat-model",
    "03-architecture/caching",
    "03-architecture/scalability",
    "03-architecture/security",
    "03-architecture/decisions",
    "04-machine-learning/cost-prediction",
    "04-machine-learning/latency-prediction",
    "04-machine-learning/quality-prediction",
    "04-machine-learning/recommendation",
    "04-machine-learning/prompt-optimization",
    "05-data-engineering/schemas",
    "05-data-engineering/pipelines",
    "05-data-engineering/etl",
    "05-data-engineering/feature-engineering",
    "05-data-engineering/data-quality",
    "05-data-engineering/data-dictionary",
    "06-api/openapi",
    "06-api/endpoints",
    "06-api/webhooks",
    "06-api/sdks",
    "07-infrastructure/deployment",
    "07-infrastructure/ci-cd",
    "07-infrastructure/observability",
    "07-infrastructure/logging",
    "07-infrastructure/monitoring",
    "07-infrastructure/alerts",
    "07-infrastructure/disaster-recovery",
    "08-experiments/week-01",
    "08-experiments/week-02",
    "08-experiments/week-03",
    "08-experiments/week-04",
    "09-benchmarks/prediction",
    "09-benchmarks/latency",
    "09-benchmarks/providers",
    "09-benchmarks/optimization",
    "10-adrs",
    "11-risks",
    "12-weekly-reviews/week-01",
    "12-weekly-reviews/week-02",
    "12-weekly-reviews/week-03",
    "12-weekly-reviews/week-04",
    "13-roadmap",
    "assets/images",
    "assets/diagrams",
    "assets/slides",
]
miss = [r for r in req if not (docs / r).is_dir()]
emptyish = []
for r in req:
    d = docs / r
    if d.is_dir() and not any(d.glob("*.md")) and not any(d.glob(".gitkeep")):
        emptyish.append(r)
print("MISSING", miss or "none")
print("NO_MD_OR_GITKEEP", emptyish or "none")
print("openapi", (docs / "06-api/openapi/openapi.yaml").exists())
print("adrs", sorted(p.name for p in (docs / "10-adrs").glob("ADR-*.md")))
print("gitkeep", len(list(docs.rglob(".gitkeep"))))
print("risk", (docs / "11-risks/risk-register.md").exists())
