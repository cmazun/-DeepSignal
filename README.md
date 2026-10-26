# DeepSignal

**The world's data. Decoded.**

A public, open-source visual data explorer and automated discovery engine.

## What is included
- Responsive static website hosted with GitHub Pages
- Scheduled World Bank indicator collection
- DuckDB-powered storage and correlation screening
- Interactive Plotly visualizations with sources and cautionary notes
- Automated deployment using GitHub Actions

## Setup
1. Repository **Settings → Pages → Build and deployment → Source: GitHub Actions**.
2. In **Actions**, run **Refresh data and deploy** manually once.
3. The workflow also refreshes data weekly.

This starter is a research prototype, not a causal inference engine. Correlations are exploratory and can be spurious. The pipeline requires at least 12 overlapping annual observations and reports sample size and Pearson r. Future releases will add multiple-testing correction, detrending, and more rigorous validation.

Note: this repository is named `-DeepSignal` (with a leading hyphen), so the Pages URL is expected to be `https://cmazun.github.io/-DeepSignal/`.
