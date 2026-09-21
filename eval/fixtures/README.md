# Frozen model-quality fixture sets (plan §8.1)

One directory per set, named `<purpose>-v<N>`. Freeze a set **before** any run that counts:

    python -c "from pathlib import Path; from valops.eval.fixtures import freeze; print(freeze(Path('eval/fixtures/judge-adversarial-v1'), 'PO'))"

`FROZEN.json` records the hash. A run against a set whose hash changed counts for nothing;
changing a set means creating `-v<N+1>`. MQ gates run each fixture P-23 times and pass on
the Wilson lower confidence bound (`valops.eval.stats`).
