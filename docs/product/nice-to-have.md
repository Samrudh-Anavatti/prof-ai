# Nice to have

Living list of good ideas that wait on money, not just on the work: a paid service, bigger hosting, or hardware we can't fund yet. An idea that only needs building, just not now, goes in [the feature index](../features/INDEX.md) as a `planned` "Later:" row instead.

Each entry says what the idea is, why it's good, what it would need and what it depends on. When an idea is funded and planned, give it an INDEX row and delete it here. The rule for adding ideas is in [CLAUDE.md](../../CLAUDE.md).

## Voice input

**The idea.** Students talk to Prof AI instead of typing, as with a dictation app like Wispr Flow. A microphone button in the composer turns speech into text; the student reads it, fixes it if needed, and sends it as a normal message. It's speech-to-text, the opposite of "Prof AI speaks" (INDEX).

**Why it's good.** Typing is slow for younger students and on phones, and some students explain their thinking better out loud. Saying "I need two numbers that add to nine" is self-explanation (L6) for less effort than typing it.

**What it would need.**
- A speech-to-text engine. The open-source choice is OpenAI's Whisper (MIT licence): `faster-whisper` or `whisper.cpp` on a server, or Whisper in the browser through transformers.js.
  - On a server: our B1 plan (1 vCPU, 1.75 GB) can't transcribe for several students at once, so it means a bigger plan or a separate container.
  - In the browser: a model download on every device, and `'wasm-unsafe-eval'` in the CSP (an ADR 0003 amendment).
  - Azure AI Speech is the paid alternative, billed per hour of audio.
  - Chrome's built-in `SpeechRecognition` normally sends the audio to Google, which rules it out for children's voices unless it runs on the device.
- Spoken maths turned into maths: "x squared plus nine x" has to become $x^2+9x$ in the chat and the working.
- Parental consent and a privacy notice that name voice.

**Risks.**
- **R10:** a child's voice is personal data, and special-category biometric data if it's ever used to recognise who is speaking. Never store audio, never use it to identify anyone, and transcribe in memory only.
- **R16:** a server or paid engine sends the audio somewhere. Check where, and under what terms.
- **Transcripts are messages.** They go through the 2,000-character input cap, the budgets and the guard pipeline like typed text, and the student sees the transcript before it sends.

**Depends on.** Money for a bigger plan or paid speech; the guard pipeline and parental consent, as for any real student; and ideally "Prof AI speaks" (INDEX) first, so both use the same audio controls.
