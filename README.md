# Inside the Game

An AI match-intelligence system built for the Microsoft x Premier League **Inside the Game** hackathon (Oct 2026). It turns synthetic football match events into explainable, personalized match intelligence: live stats, key moments, *why* they matter, and recaps tailored to each fan.

> Status: early design. Architecture and stack are being whiteboarded.

## Pipeline

1. **Ingest**: stream synthetic match events (passes, shots, tackles, possession changes, pressure).
2. **Interpret**: aggregate events into stats, patterns and match state.
3. **Explain**: say why a moment matters, not just that it happened.
4. **Render**: produce timed, machine-readable output that can sit on screen alongside the match.
5. **Personalize**: give an analyst and a casual fan genuinely different experiences.

## Getting started

```bash
git clone https://github.com/Samrudh-Anavatti/inside-the-game.git
cd inside-the-game
cp .env.example .env
bash scripts/test.sh
```

Setup instructions will expand as the stack lands.

## Contributing

We build with coding agents. Read [CLAUDE.md](CLAUDE.md) for conventions, and [docs/features/INDEX.md](docs/features/INDEX.md) for what has been built so far.

## Team

- Sam ([@Samrudh-Anavatti](https://github.com/Samrudh-Anavatti))
- Punjy

## License

[MIT](LICENSE)
