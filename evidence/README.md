# Evidence Gold Reporting POC

This directory contains an Evidence.dev proof-of-concept for business reporting on the Aurora gold layer.

It starts from `gold.occupancy_daily_metrics` (current occupancy KPI table) and extends into move-in/move-out profiling by:
- contract type (`tenant_type`)
- nationality
- property (`apartment_name`)
- municipality

## Why this exists

The objective is to evaluate whether Evidence Cloud Hobby is sufficient for report generation and analyst workflow before adopting open-source self-hosted Evidence on AWS.

## Data model mapping

Requested table and actual implementation in this repo:
- Requested: `gold.occupancy`
- Actual: `gold.occupancy_daily_metrics`

Profiling datasets:
- `gold.new_contracts` for move-ins
- `gold.moveouts` for completed move-outs
- `gold.moveout_analysis` for richer move-out dimensions (already modeled in dbt)

## Local setup

1. Use a supported Node runtime (Evidence requirement): Node 18.13, 20, or 22.

```bash
cd evidence
nvm use 22  # or any supported LTS
```

2. Install dependencies:

```bash
npm install
```

3. Configure connection secrets via environment variables (recommended):

```bash
cp .env.example .env
# Fill in host/user/password/database and optional SSL overrides
```

4. Start Evidence dev server:

```bash
npm run dev
```

5. Open `http://localhost:3000/settings` and confirm source `aurora_gold`.

6. Extract sources:

```bash
npm run sources
```

## Commands

```bash
npm run dev       # Local development
npm run sources   # Extract source queries into Evidence datasets
npm run build     # Build static site
npm run preview   # Preview built site
```

## Expected pages

- `pages/index.md`: KPI overview and quick diagnostics
- `pages/occupancy.md`: occupancy trend and net move-in/move-out drivers
- `pages/moveins.md`: move-in profiling by tenant type, nationality, municipality, property
- `pages/moveouts.md`: move-out profiling with same dimensions and trend breakdown
- `pages/geography.md`: municipality/property concentration and churn hotspots

## Security notes

- Use a read-only MySQL user limited to `gold.*`.
- Keep Aurora in private networking where possible.
- Do not commit real credentials; `.env` and `connection.options.yaml` stay out of git.

## Decision gate checklist

Use this POC to decide Cloud Hobby vs self-hosted Evidence:
- Connectivity reliability to Aurora
- Source extraction duration (`npm run sources`)
- Page render/filter response times
- Analyst productivity for SQL/Markdown iteration
