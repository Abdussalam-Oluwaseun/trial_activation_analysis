# Outputs

This directory contains all generated outputs from the trial activation analysis project.

## Structure

```
outputs/
├── figures/    # Plots, charts, and visualizations (PNG, SVG, PDF)
├── tables/     # Exported data tables and summaries (CSV, Excel)
├── reports/    # Generated reports and documents (HTML, PDF, Markdown)
└── models/     # Serialized model artifacts (PKL, JOBLIB, JSON)
```

## Guidelines

- **figures/** — Save all matplotlib/seaborn/plotly outputs here.
- **tables/** — Save cleaned datasets, aggregated summaries, and statistical outputs here.
- **reports/** — Save final analysis reports or notebook exports here.
- **models/** — Save any trained model files or pipeline objects here.

> **Note:** Raw data files should remain in the source data directory and must NOT be saved here.
