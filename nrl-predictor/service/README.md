# nrl.json feed service

Static feed server for the dashboard artifact — same pattern as `pnl-dashboard`.

Endpoints: `/nrl.json` (the feed), `/health`.

## Deploy to Railway (one-time, from the Mac)

```bash
cd nrl-predictor
railway init --name nrl-feed          # or link to an existing project
railway up                            # uses ./railway.json -> service/main.py
```

Then set the deploy trigger to this repo's `main` branch in the Railway dashboard
(same as the bot fleet). Each push re-bakes `outputs/nrl.json` into the deploy.
No env vars needed; Railway injects `PORT`.

Weekly refresh is just: `python -m src.cli refresh && python -m src.cli predict &&
python -m src.cli odds && python -m src.cli feed` then commit+push (Cowork task
owns the schedule).
