# Prof AI

An AI-assisted tutoring platform for grades 6–12, built around a human tutor. The tutor teaches the lesson. Between lessons, students do assigned questions with software/AI marking and get help from their own guarded study assistant, grounded in the tutor's content. The tutor sees results, transcripts and usage.

> Status: early design. See [docs/product/](docs/product/vision.md) for the vision, architecture and risks.

## Getting started

```bash
git clone https://github.com/Samrudh-Anavatti/prof-ai.git
cd prof-ai
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # .venv/bin/python on macOS/Linux
cp .env.example .env
bash scripts/test.sh
.venv/Scripts/python -m uvicorn prof_ai.main:app --app-dir src --reload
```

Live at https://prof-ai.azurewebsites.net (placeholder for now).

## Contributing

We build with coding agents. Read [CLAUDE.md](CLAUDE.md) for conventions, and [docs/features/INDEX.md](docs/features/INDEX.md) for what has been built so far.

## Team

- Sam ([@Samrudh-Anavatti](https://github.com/Samrudh-Anavatti))
- Punjy

## License

[MIT](LICENSE)
