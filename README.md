# 🔥 Campaign Roaster AI

**Pre-test any marketing campaign before it gets a budget.**

Paste the ad copy and the target audience. The app runs the checks a marketer would do on paper before spending money: a strategy checklist, an AIDA score, warning signs, and A/B variants worth testing. It ends with a go / no-go verdict and a small test plan.

👉 **[Try the live app](https://campaign-roaster-ai.streamlit.app/)** (no campaign handy? click one of the samples)

---

## Why I built this

Most campaigns that flop could have been caught before launch. Marketers call this **pre-testing**: review the idea on paper, test it with real people, then test it in market with a small budget before committing the full spend.

This tool automates the first step. It doesn't replace testing with real people, but it catches weak ideas early and tells you exactly what to test next.

## What it checks

**1. Strategy checklist (pass / risky / fail)**
| Check | The question it asks |
|---|---|
| Clear objective | Can you say in one sentence what the campaign should achieve? |
| Specific audience | Is it written for a sharp audience, not "everyone aged 18-45"? |
| One clear message | Does it say one thing, instead of five things nobody remembers? |
| **Cover-the-logo test** | Hide the brand name. Could a competitor run this exact ad? |
| Fits the brand | Does it match how people already see the brand? |
| Culturally safe | Could anything offend, be misread or trigger backlash? |

**2. AIDA score.** Attention, Interest, Desire and Action, each scored out of 10, plus emotional pull and CTA strength.

**3. Warning signs.** Red flags such as "people may remember the joke but not the brand."

**4. Three A/B variants.** Each one tests a different hypothesis (for example emotion vs urgency vs humour), with a recommended lead variant and a chart comparing it against the original.

**5. Go / no-go verdict.** Decided by fixed rules written into the code, not by the AI. The AI gives the scores; the rules give the verdict, so a campaign can't talk its way past weak results.

| Verdict | Rule |
|---|---|
| 🔴 Back to the drawing board | Score 3 or below, or fails the cultural safety check |
| 🟢 Ready for a small test | Score 7+, no failed checks, at least 5 of 6 checks passed |
| 🟡 Rework before testing | Everything else |

**6. Small test plan.** Where to run the test, how much budget, how long, the winning metric and the go criteria.

## Built with

- **Python + Streamlit** for the app
- **Google Gemini API** for the analysis, returning structured JSON
- **Plotly** for the AIDA chart
- **Streamlit Cloud** for hosting

## Run it locally

```bash
pip install -r requirements.txt
```

Create `.streamlit/secrets.toml` with your free Gemini API key:

```toml
GEMINI_API_KEY = "your-key-here"
```

Then run:

```bash
streamlit run app.py
```

## Limits

Scores come from an AI model, so treat them as a first opinion, not a final judgement. Real behaviour (clicks, sign-ups, sales) is always the better test.

---

Part of my marketing portfolio · [GitHub](https://github.com/vanshika-nagvani) · [LinkedIn](https://linkedin.com/in/vanshika-nagvani)

*Built by Vanshika Nagvani*
