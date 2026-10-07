# Hackathon brief

Source: [microsoft/insidethegamehackathon](https://github.com/microsoft/insidethegamehackathon) (official rules). Event site: https://aka.ms/insidethegame

## Key dates (Pacific Time)

| What | When |
|------|------|
| Registration closes | **Tue 20 Oct 2026, 12:00 PT**. Register the team and pick one Representative |
| Submission deadline | **Tue 27 Oct 2026, 23:59 PT** (Wed 28 Oct morning in UK/EU, evening in AU) |
| Judging | 27 Oct to 10 Nov 2026. The demo must stay live and free to access |
| Winners announced | By 20 Nov 2026 |

## The challenge

Build an AI-driven app or agents that turn **synthetic** football events into explainable match intelligence, real-time narratives and automated recaps for studio, broadcast or streaming, personalized for any fan.

One pipeline, five stages: **Ingest → Interpret → Explain → Render → Personalize**.

Suggested features:
- Player identification: name tagging, plus speed and distance indicators when thresholds are hit
- Pass quality: distance, accuracy and a difficulty rating
- Speed metrics: ball speed and shot speed
- Auto-eventing: a model over a video feed that generates these metrics automatically
- Narratives: key moments, player-performance context, milestones and recaps
- Explainability: control vs chaos, tactical pressure changes, game rhythm
- Data innovation: create or extend synthetic event datasets
- Multi-language output
- Personalization: favorite club or player, player-focus mode, analyst vs casual fan modes

## Submission requirements

- A new project, started after 29 Sep 2026
- **Public GitHub repo**
- An elevator pitch: what it does, the problem it solves, and which Microsoft and Azure tech it uses
- A **demo video under 2 minutes** (YouTube or Vimeo) showing it running, with no third-party trademarks or copyrighted music
- A working demo link or test build for judges, free and without restriction until judging ends
- All materials in English
- Teams of up to 4

## Judging (20% each)

1. **Technological implementation**: synthetic data quality, software practices, use of the hero tech (Microsoft Foundry, Agent Framework, Azure MCP, GitHub Copilot Agent Mode, Fabric, Azure AI Services, Azure databases)
2. **Agentic design and innovation**: orchestration, MCP, multi-agent collaboration
3. **Real-world impact**: production-deployable? meaningful problem?
4. **UX and presentation**: intuitive UX, a clear video, a balance of frontend and backend
5. **Category adherence**

Tie-break order follows the list above, so tech implementation counts most.

## Prizes

The grand prize is 1st or 2nd place. One category prize is possible on top:
- Best use of Microsoft Foundry
- Best enterprise solution
- Best multi-agent system (GitHub Copilot, Microsoft Agent Framework, A2A): distinct agent roles, shared state, handoffs, failure recovery
- Best Azure cloud-native integration (AKS, Container Apps, Functions, Logic Apps; event-driven)

## Rules that bite

- Synthetic data only. We source and generate it ourselves; no real footage is provided.
- No Premier League or club trademarks in the app or video unless we have permission.
- Open-source dependencies are fine, but our code must build meaningfully on them.
