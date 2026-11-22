# Epicenter

Collector Crypt gacha cheatsheet: type a bankroll, get the machine most likely
to grow it. Live at **https://epicenter.saprozoic.dev**.

- Data: [Knut's Gap Tracker](https://gap.knutegil.dev/inventory), pulled twice
  a day by `.github/workflows/update.yml` (requests spaced 0.4 s apart).
- `sim/` - the pull, the 30k-session simulations, and the page template.
- `state/` - last pull and last results, used for the "What changed" summary.
- `index.html` - the built page GitHub Pages serves (written by the workflow).

Fan-made. Not affiliated with Collector Crypt or the tracker. Not financial advice.
