import json
import re
import time

import plotly.graph_objects as go
import streamlit as st
from google import genai
from google.genai import errors, types

# If Google renames the model again, this is the only line to change.
MODEL_NAME = "gemini-3.8-flash"
# Tried in order if the main model is busy or unavailable.
FALLBACK_MODELS = ["gemini-flash-latest"]

st.set_page_config(page_title="Campaign Roaster AI", page_icon="🔥", layout="centered")

# ---------------------------------------------------------------------------
# Sample campaigns (fictional brands, written for this demo)
# ---------------------------------------------------------------------------
SAMPLES = {
    "Cold coffee launch": {
        "brand": "Brew Bros",
        "audience": "College students and young professionals in metro cities, 18-26",
        "campaign": "Introducing Brew Bros Cold Coffee. Made with premium beans. "
        "Available in 3 flavours. Buy now at your nearest store.",
    },
    "Skincare festive sale": {
        "brand": "Glowmint",
        "audience": "Working women aged 24-34 who already use a basic skincare routine",
        "campaign": "This Diwali, glow like never before! Flat 40% off on all Glowmint "
        "products. Because you deserve to shine. Limited time only. Shop now!",
    },
    "Fintech app install": {
        "brand": "PaisaPal",
        "audience": "First-time earners aged 21-27 who have never invested",
        "campaign": "Start investing with just ₹100. PaisaPal makes wealth creation "
        "simple, safe and smart. Download the app today.",
    },
}


def load_sample(name):
    sample = SAMPLES[name]
    st.session_state["brand"] = sample["brand"]
    st.session_state["audience"] = sample["audience"]
    st.session_state["campaign"] = sample["campaign"]


# The six strategy checks a marketer runs on paper before testing with people.
CHECKS = {
    "objective": "Clear objective",
    "audience": "Specific audience",
    "single_minded": "One clear message",
    "distinctive": "Cover-the-logo test",
    "brand_fit": "Fits the brand",
    "cultural_safety": "Culturally safe",
}
CHECK_HELP = {
    "objective": "Can you say in one sentence what this campaign should achieve?",
    "audience": "Is it written for a sharp audience, not 'everyone aged 18-45'?",
    "single_minded": "Does it say one thing, instead of five things nobody remembers?",
    "distinctive": "Hide the brand name. Could a competitor run this exact ad?",
    "brand_fit": "Does it match how people already see the brand?",
    "cultural_safety": "Could anything offend, be misread or trigger backlash?",
}
STAGES = ["attention", "interest", "desire", "action"]

# ---------------------------------------------------------------------------
# Gemini call
# ---------------------------------------------------------------------------
SCHEMA = """{
  "overall_score": 0,
  "verdict": "one short line summing up the campaign",
  "checklist": {
    "objective":       {"status": "pass | risky | fail", "why": "one line"},
    "audience":        {"status": "pass | risky | fail", "why": "one line"},
    "single_minded":   {"status": "pass | risky | fail", "why": "one line"},
    "distinctive":     {"status": "pass | risky | fail", "why": "one line: could a competitor run this ad unchanged?"},
    "brand_fit":       {"status": "pass | risky | fail", "why": "one line"},
    "cultural_safety": {"status": "pass | risky | fail", "why": "one line"}
  },
  "warning_signs": ["0-3 red flags, e.g. 'People may remember the joke but not the brand'"],
  "aida": {
    "attention": {"score": 0, "why": "one line"},
    "interest":  {"score": 0, "why": "one line"},
    "desire":    {"score": 0, "why": "one line"},
    "action":    {"score": 0, "why": "one line"}
  },
  "emotional_pull": {"score": 0, "why": "one line"},
  "cta_strength":   {"score": 0, "why": "one line"},
  "working": ["2-3 specific strengths"],
  "weak": ["2-3 specific problems"],
  "roast": "2-3 sharp, witty sentences. Honest, never mean about people.",
  "variants": [
    {
      "name": "short label, e.g. Emotional",
      "tests": "the one hypothesis this version tests, in one line",
      "copy": "the full variant copy, similar length to the original",
      "aida": {"attention": 0, "interest": 0, "desire": 0, "action": 0},
      "score": 0
    }
  ],
  "recommended_variant": 0,
  "test_plan": {
    "channel": "where to run the test, e.g. Instagram Reels ads on Meta",
    "budget": "share of total budget for testing, e.g. 5-10%",
    "duration": "e.g. 5-7 days",
    "metric": "the one metric that decides the winner",
    "go_criteria": "what result means roll it out, stated relative to the other variants or the brand's past campaigns"
  },
  "big_idea": "one bold new creative direction in 2-3 sentences"
}"""


def build_prompt(brand, audience, campaign):
    return (
        "You are a sharp senior marketing strategist with 15 years of experience "
        "at top consumer brands in India. Pre-test the campaign below before it "
        "gets a full budget: run the strategy checklist, score it with AIDA, flag "
        "warning signs, then write variants worth A/B testing.\n\n"
        f"Brand: {brand or 'Not given'}\n"
        f"Target audience: {audience or 'Not given'}\n"
        f"Campaign copy: {campaign}\n\n"
        "Rules:\n"
        "- All scores are whole numbers from 0 to 10. Be strict: 5 is average.\n"
        "- Checklist status must be exactly one of: pass, risky, fail.\n"
        "- Write 3 variants. Each one must test a DIFFERENT hypothesis "
        "(for example emotion vs urgency vs humour), not three versions of the same idea.\n"
        "- Variant quality bar: write like the best creative agencies in India. Every "
        "variant must be built on one specific, true human insight about the audience, "
        "and must stay true to what the brand already stands for. Show, don't tell.\n"
        "- Never use these patterns in variants: the 'Did X happen? Then [tagline]' "
        "formula; sitcom setups; forced Hinglish wordplay; family or gender stereotypes "
        "(e.g. daughters making rotis, sons as troublemakers); generic lines like "
        "'because you deserve it' or 'like never before'; jargon the audience wouldn't say.\n"
        "- If the original is already strong (score 7+), keep its core idea or tagline and "
        "use the variants to test new executions of it, not replacements.\n"
        "- Before you answer, reread each variant and replace any that breaks these rules "
        "or that a senior creative director would reject.\n"
        "- Score variants as a skeptical outside judge, not their author. A variant scores "
        "higher than the original only if it is clearly better. AI rewrites of famous, "
        "proven campaigns are usually weaker, so score them that way.\n"
        "- recommended_variant is the 0-based index of the strongest variant.\n"
        "- In the test plan, never invent industry benchmark numbers. State go criteria "
        "relative to the other variants or to the brand's own past campaigns.\n"
        "- Write for the stated audience. Keep Indian market context in mind.\n\n"
        "Reply with JSON only, exactly in this shape:\n" + SCHEMA
    )


@st.cache_resource
def get_client():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])


def clamp(value):
    try:
        return max(0, min(10, round(float(value))))
    except (TypeError, ValueError):
        return 0


def as_dict(value):
    return value if isinstance(value, dict) else {}


def as_list(value):
    return [str(v) for v in value if v] if isinstance(value, list) else []


def parse_response(text):
    """Turn Gemini's reply into a clean dict, even if it wraps it in ```json fences."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    data = json.loads(cleaned)

    checklist = {}
    for key in CHECKS:
        item = as_dict(as_dict(data.get("checklist")).get(key))
        status = str(item.get("status", "")).strip().lower()
        checklist[key] = {
            "status": status if status in ("pass", "risky", "fail") else "risky",
            "why": item.get("why", ""),
        }

    aida = as_dict(data.get("aida"))
    variants = []
    for v in data.get("variants", []) if isinstance(data.get("variants"), list) else []:
        v = as_dict(v)
        if not v.get("copy"):
            continue
        v_aida = as_dict(v.get("aida"))
        variants.append(
            {
                "name": v.get("name", "Variant"),
                "tests": v.get("tests", ""),
                "copy": v["copy"],
                "aida": {s: clamp(v_aida.get(s)) for s in STAGES},
                "score": clamp(v.get("score")),
            }
        )
    variants = variants[:3]

    try:
        recommended = int(data.get("recommended_variant", 0))
    except (TypeError, ValueError):
        recommended = 0
    if not 0 <= recommended < len(variants):
        recommended = max(range(len(variants)), key=lambda i: variants[i]["score"]) if variants else 0

    plan = as_dict(data.get("test_plan"))
    return {
        "overall_score": clamp(data.get("overall_score")),
        "verdict": data.get("verdict", ""),
        "checklist": checklist,
        "warning_signs": as_list(data.get("warning_signs")),
        "aida": {
            s: {"score": clamp(as_dict(aida.get(s)).get("score")), "why": as_dict(aida.get(s)).get("why", "")}
            for s in STAGES
        },
        "emotional_pull": {
            "score": clamp(as_dict(data.get("emotional_pull")).get("score")),
            "why": as_dict(data.get("emotional_pull")).get("why", ""),
        },
        "cta_strength": {
            "score": clamp(as_dict(data.get("cta_strength")).get("score")),
            "why": as_dict(data.get("cta_strength")).get("why", ""),
        },
        "working": as_list(data.get("working")),
        "weak": as_list(data.get("weak")),
        "roast": data.get("roast", ""),
        "variants": variants,
        "recommended": recommended,
        "test_plan": {k: plan.get(k, "") for k in ("channel", "budget", "duration", "metric", "go_criteria")},
        "big_idea": data.get("big_idea", ""),
    }


# Same inputs = instant answer from cache instead of a new API call.
def call_gemini(prompt):
    """Retry when Gemini is busy, then fall back to the next model."""
    last_error = None
    for model in [MODEL_NAME, *FALLBACK_MODELS]:
        for attempt in range(3):
            try:
                return get_client().models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.7,
                    ),
                )
            except errors.APIError as e:
                last_error = e
                if e.code in (429, 500, 503, 504):  # busy or rate-limited: wait, retry
                    time.sleep(2 * (attempt + 1))
                    continue
                if e.code == 404:  # model name not found: try the next model
                    break
                raise
    raise last_error


@st.cache_data(show_spinner=False, ttl=60 * 60 * 6)
def roast_campaign(brand, audience, campaign):
    response = call_gemini(build_prompt(brand, audience, campaign))
    return parse_response(response.text)


# ---------------------------------------------------------------------------
# Go / no-go: fixed rules, decided in code before anyone sees the results.
# The AI scores the campaign; it does not get to pick the verdict.
# ---------------------------------------------------------------------------
GO_RULES = """
- **Back to the drawing board** if the score is 3 or below, or the campaign fails the cultural safety check.
- **Ready for a small test** if the score is 7 or above, no check fails and at least 5 of the 6 checks pass.
- **Rework before testing** in every other case.
"""


def decide(result):
    checks = result["checklist"]
    fails = [CHECKS[k] for k, v in checks.items() if v["status"] == "fail"]
    score = result["overall_score"]

    if score <= 3 or checks["cultural_safety"]["status"] == "fail":
        reason = "Cultural safety check failed." if checks["cultural_safety"]["status"] == "fail" else f"Score is {score}/10."
        return "kill", "Back to the drawing board", reason
    risky = [CHECKS[k] for k, v in checks.items() if v["status"] == "risky"]

    if score >= 7 and not fails and len(risky) <= 1:
        return "go", "Ready for a small test", "Strong score and no failed checks. Test it with a small budget before the full launch."
    if fails:
        return "rework", "Rework before testing", "Failed: " + ", ".join(fails) + "."
    if len(risky) > 1:
        return "rework", "Rework before testing", "Too many risky checks: " + ", ".join(risky) + "."
    return "rework", "Rework before testing", f"Score is {score}/10. Aim for 7+ before spending on a test."


# ---------------------------------------------------------------------------
# Visual pieces
# ---------------------------------------------------------------------------
STATUS_STYLE = {
    "pass": ("✅", "Pass"),
    "risky": ("⚠️", "Risky"),
    "fail": ("❌", "Fail"),
}


def score_band(score):
    if score >= 7:
        return "Strong", "#0ca30c"
    if score >= 4:
        return "Needs work", "#fab219"
    return "Weak", "#d03b3b"


def score_meter(score, label):
    band, color = score_band(score)
    st.markdown(
        f"""
        <div style="margin-bottom:4px;font-size:0.9rem;opacity:0.75">{label}</div>
        <div style="font-size:3.4rem;font-weight:700;line-height:1">
          {score}<span style="font-size:1.4rem;font-weight:500;opacity:0.6"> / 10</span>
        </div>
        <div role="meter" aria-valuemin="0" aria-valuemax="10" aria-valuenow="{score}"
             aria-label="{label}: {score} out of 10"
             style="height:10px;border-radius:5px;background:rgba(137,135,129,0.25);
                    margin:12px 0 6px 0;overflow:hidden">
          <div style="width:{score * 10}%;height:100%;border-radius:5px;background:{color}"></div>
        </div>
        <div style="font-size:0.9rem;font-weight:600">{band}</div>
        """,
        unsafe_allow_html=True,
    )


def aida_chart(original, variant_aida, variant_label):
    stages = [s.title() for s in STAGES]
    original_scores = [original[s]["score"] for s in STAGES]
    variant_scores = [variant_aida[s] for s in STAGES]

    fig = go.Figure()
    for name, scores, color in [
        ("Original", original_scores, "#898781"),
        (variant_label, variant_scores, "#2a78d6"),
    ]:
        fig.add_bar(
            name=name,
            y=stages,
            x=scores,
            orientation="h",
            marker=dict(color=color, cornerradius=4),
            text=scores,
            textposition="outside",
            hovertemplate=f"{name} · %{{y}}: %{{x}}/10<extra></extra>",
        )
    fig.update_layout(
        barmode="group",
        bargap=0.35,
        bargroupgap=0.12,
        height=320,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, traceorder="normal"),
        xaxis=dict(range=[0, 11], dtick=2, showgrid=True, zeroline=False, title=None),
        yaxis=dict(autorange="reversed", title=None),
        uniformtext=dict(mode="hide", minsize=10),
    )
    return fig


def build_report(brand, campaign, r, decision):
    _, label, reason = decision
    lines = [
        f"# Campaign Pre-Check: {brand or 'Untitled campaign'}",
        "",
        f"**Verdict:** {label}. {reason}",
        f"**Score:** {r['overall_score']}/10. {r['verdict']}",
        "",
        "## Strategy checklist",
    ]
    for key, name in CHECKS.items():
        item = r["checklist"][key]
        lines.append(f"- {STATUS_STYLE[item['status']][1]}: {name}. {item['why']}")
    if r["warning_signs"]:
        lines += ["", "## Warning signs", *[f"- {w}" for w in r["warning_signs"]]]
    lines += ["", "## AIDA"]
    for stage in STAGES:
        lines.append(f"- {stage.title()}: {r['aida'][stage]['score']}/10. {r['aida'][stage]['why']}")
    lines += [
        "",
        f"**Emotional pull:** {r['emotional_pull']['score']}/10. {r['emotional_pull']['why']}",
        f"**CTA strength:** {r['cta_strength']['score']}/10. {r['cta_strength']['why']}",
        "",
        "## What's working",
        *[f"- {item}" for item in r["working"]],
        "",
        "## What's weak",
        *[f"- {item}" for item in r["weak"]],
        "",
        "## The roast",
        r["roast"],
        "",
        "## Original",
        campaign,
        "",
        "## Variants to A/B test",
    ]
    original_wins = bool(r["variants"]) and r["variants"][r["recommended"]]["score"] <= r["overall_score"]
    if original_wins:
        lines += ["None of the variants beat the original. Keep it as the lead and test these as challengers.", ""]
    for i, v in enumerate(r["variants"]):
        tag = " (lead variant)" if i == r["recommended"] and not original_wins else ""
        lines += [f"### {chr(65 + i)}: {v['name']}{tag} · {v['score']}/10", f"Tests: {v['tests']}", "", v["copy"], ""]
    plan = r["test_plan"]
    lines += [
        "## Test plan",
        f"- Channel: {plan['channel']}",
        f"- Budget: {plan['budget']}",
        f"- Duration: {plan['duration']}",
        f"- Winning metric: {plan['metric']}",
        f"- Go criteria: {plan['go_criteria']}",
        "",
        "## One big idea",
        r["big_idea"],
        "",
        "---",
        "AI pre-check only. Test with real people before committing the full budget.",
        "Made with Campaign Roaster AI by Vanshika Nagvani · github.com/vanshika-nagvani",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
st.title("🔥 Campaign Roaster AI")
st.subheader("Pre-test any campaign before it gets a budget.")
st.write(
    "Paste the copy. Get a strategy checklist, an AIDA score, A/B variants worth "
    "testing and a go / no-go verdict."
)
st.caption("Built by Vanshika Nagvani | github.com/vanshika-nagvani")

st.write("**No campaign handy? Try a sample:**")
sample_cols = st.columns(len(SAMPLES))
for col, name in zip(sample_cols, SAMPLES):
    col.button(name, on_click=load_sample, args=(name,), width="stretch")

st.divider()

brand = st.text_input("Brand name", key="brand", placeholder="e.g. Blinkit, Zepto, BellaVita")
campaign = st.text_area(
    "Campaign copy or brief",
    key="campaign",
    height=160,
    placeholder="Paste the ad copy, caption or brief here",
)
audience = st.text_input(
    "Target audience", key="audience", placeholder="e.g. Urban millennials in Delhi aged 25-35"
)

if st.button("🔥 Pre-test this campaign", type="primary", width="stretch"):
    if not campaign.strip():
        st.error("Paste a campaign first, or pick one of the samples above.")
    else:
        try:
            with st.spinner("Checking strategy, scoring AIDA and writing variants... (takes about 20 seconds)"):
                st.session_state["result"] = roast_campaign(brand.strip(), audience.strip(), campaign.strip())
                st.session_state["result_inputs"] = (brand.strip(), campaign.strip())
        except json.JSONDecodeError:
            st.error("The AI sent back an answer the app couldn't read. Click Pre-test again.")
        except KeyError:
            st.error("The Gemini API key is missing. Add GEMINI_API_KEY in the app's Secrets.")
        except errors.APIError as e:
            if e.code == 429:
                st.warning(
                    "⏳ Too many requests to the free Gemini API right now. "
                    "Wait a minute and click Pre-test again."
                )
            elif e.code in (500, 503, 504):
                st.warning(
                    "⏳ Google's Gemini servers are busy right now. This is on Google's side, "
                    "not the app. Wait a minute and click Pre-test again."
                )
            else:
                st.error(f"Gemini returned an error ({e.code}). Try again in a minute.")
        except Exception as e:
            st.error(f"Something went wrong: {e}")

result = st.session_state.get("result")
if result:
    shown_brand, shown_campaign = st.session_state["result_inputs"]
    decision = decide(result)
    kind, label, reason = decision
    checks = result["checklist"]
    passed = sum(1 for v in checks.values() if v["status"] == "pass")

    st.divider()

    # 1. Verdict first
    banner = {"go": st.success, "rework": st.warning, "kill": st.error}[kind]
    icon = {"go": "🟢", "rework": "🟡", "kill": "🔴"}[kind]
    banner(f"**{icon} {label}.** {reason}")
    with st.expander("How the verdict is decided"):
        st.markdown(
            "The rules are fixed in advance, so a campaign we like can't talk its way past "
            "weak results. The AI gives the scores; these rules give the verdict." + GO_RULES
        )

    # 2. Scores
    left, right = st.columns([1.2, 1], gap="large")
    with left:
        score_meter(result["overall_score"], "Campaign score")
        if result["verdict"]:
            st.caption(result["verdict"])
    with right:
        st.metric("Strategy checks passed", f"{passed}/6")
        st.metric("Emotional pull", f"{result['emotional_pull']['score']}/10")
        st.caption(result["emotional_pull"]["why"])
        st.metric("CTA strength", f"{result['cta_strength']['score']}/10")
        st.caption(result["cta_strength"]["why"])

    # 3. Strategy checklist
    st.markdown("### Strategy checklist")
    st.caption("Tap or hover the ? next to a check to see what it asks.")
    with st.container(border=True):
        for key, name in CHECKS.items():
            item = checks[key]
            icon_s, status_label = STATUS_STYLE[item["status"]]
            st.markdown(f"{icon_s} **{status_label} · {name}**  \n{item['why']}", help=CHECK_HELP[key])

    # 4. Warning signs
    if result["warning_signs"]:
        st.markdown("### 🚩 Warning signs")
        for sign in result["warning_signs"]:
            st.markdown(f"- {sign}")

    # 5. AIDA
    variants = result["variants"]
    lead = variants[result["recommended"]] if variants else None
    lead_letter = chr(65 + result["recommended"])
    original_wins = bool(lead) and lead["score"] <= result["overall_score"]
    if lead:
        if original_wins:
            st.markdown(f"### AIDA: original vs best challenger (variant {lead_letter})")
        else:
            st.markdown(f"### AIDA: original vs variant {lead_letter}")
        st.plotly_chart(
            aida_chart(result["aida"], lead["aida"], f"Variant {lead_letter}: {lead['name']}"),
            width="stretch",
            config={"displayModeBar": False},
        )
    with st.expander("Why each AIDA score"):
        rows = ["| Stage | Original | Why |", "|---|---|---|"]
        for stage in STAGES:
            rows.append(
                f"| {stage.title()} | {result['aida'][stage]['score']}/10 | {result['aida'][stage]['why']} |"
            )
        st.markdown("\n".join(rows))

    # 6. Working / weak
    good, bad = st.columns(2, gap="large")
    with good:
        st.markdown("### ✅ What's working")
        for item in result["working"]:
            st.markdown(f"- {item}")
    with bad:
        st.markdown("### ⚠️ What's weak")
        for item in result["weak"]:
            st.markdown(f"- {item}")

    # 7. Roast
    st.markdown("### 🔥 The roast")
    st.markdown(f"> {result['roast']}")

    # 8. Variants
    if variants:
        st.markdown("### 🧪 Variants to A/B test")
        if original_wins:
            st.info(
                "None of the variants beat the original. Keep it as your lead and run "
                "these as challengers. If one wins with real people, that's a real insight."
            )
        else:
            st.caption(
                "Each version tests a different idea. Run them side by side with a small "
                "budget and let real clicks pick the winner."
            )
        with st.container(border=True):
            tag = "  ⭐ Keep this as the lead" if original_wins else ""
            st.markdown(f"**Original · {result['overall_score']}/10**{tag}")
            st.write(shown_campaign)
        for i, v in enumerate(variants):
            with st.container(border=True):
                tag = "  ⭐ Lead with this one" if i == result["recommended"] and not original_wins else ""
                st.markdown(f"**Variant {chr(65 + i)}: {v['name']} · {v['score']}/10**{tag}")
                st.caption(f"Tests: {v['tests']}")
                st.write(v["copy"])

    # 9. Test plan
    plan = result["test_plan"]
    if any(plan.values()):
        st.markdown("### 📋 Small test plan")
        with st.container(border=True):
            st.markdown(
                "  \n".join(
                    [
                        f"**Where:** {plan['channel']}",
                        f"**Budget:** {plan['budget']}",
                        f"**How long:** {plan['duration']}",
                        f"**Winning metric:** {plan['metric']}",
                        f"**Go if:** {plan['go_criteria']}",
                    ]
                )
            )

    # 10. Big idea
    st.markdown("### 💡 One big idea")
    st.info(result["big_idea"])

    st.download_button(
        "Download this pre-check",
        data=build_report(shown_brand, shown_campaign, result, decision),
        file_name=f"campaign-precheck-{(shown_brand or 'campaign').lower().replace(' ', '-')}.md",
        mime="text/markdown",
        width="stretch",
    )

st.divider()
st.caption(
    "This is an AI pre-check, not a replacement for testing with real people. "
    "Use it to catch weak ideas early, then test in market with a small budget."
)
