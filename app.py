import datetime
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


# Suggestions for the brand dropdown. Any other brand can still be typed in.
BRANDS = sorted(
    {
        # Food, snacks and beverages
        "Amul", "Britannia", "Parle", "Haldiram's", "Bikaji", "Maggi", "Nestlé",
        "Cadbury Dairy Milk", "KitKat", "Lay's", "Kurkure", "Bingo!", "Sunfeast",
        "Yippee", "Tata Tea", "Red Label", "Taj Mahal Tea", "Bru", "Nescafé",
        "Horlicks", "Bournvita", "Mother Dairy", "Saffola", "Fortune", "Aashirvaad",
        "Tata Salt", "MDH", "Everest", "Patanjali", "Dabur", "Paper Boat", "Epigamia",
        "Licious", "iD Fresh Food", "Kwality Wall's", "Havmor", "Coca-Cola", "Thums Up",
        "Sprite", "Limca", "Maaza", "Frooti", "Pepsi", "Mountain Dew", "7UP", "Slice",
        "Bisleri", "Red Bull", "Campa Cola", "Bira 91",
        # Beauty and personal care
        "Lakmé", "Nykaa", "Mamaearth", "SUGAR Cosmetics", "Plum", "The Derma Co",
        "Minimalist", "Lotus Herbals", "Biotique", "Himalaya", "Dove", "Lux",
        "Lifebuoy", "Pears", "Santoor", "Dettol", "Colgate", "Pepsodent", "Close-Up",
        "Clinic Plus", "Head & Shoulders", "Pantene", "Garnier", "L'Oréal Paris",
        "Maybelline", "Nivea", "Pond's", "Vaseline", "Glow & Lovely", "Gillette",
        "Bombay Shaving Company", "Beardo", "Fogg", "Wild Stone", "Axe", "Park Avenue",
        "Bella Vita", "Forest Essentials", "Kama Ayurveda", "Boroplus",
        # Home
        "Surf Excel", "Ariel", "Tide", "Rin", "Vim", "Harpic", "Lizol", "Good Knight",
        "Asian Paints", "Berger Paints", "Fevicol",
        # Quick commerce, food delivery and e-commerce
        "Blinkit", "Zepto", "Swiggy", "Swiggy Instamart", "Zomato", "BigBasket",
        "Flipkart", "Amazon India", "Myntra", "Ajio", "Meesho", "Nykaa Fashion",
        "Tata CLiQ", "JioMart", "FirstCry", "Lenskart", "Urban Company", "PharmEasy",
        "Tata 1mg", "Cult.fit",
        # Fintech, banking and insurance
        "Paytm", "PhonePe", "Google Pay", "CRED", "Zerodha", "Groww", "Upstox",
        "HDFC Bank", "ICICI Bank", "SBI", "Axis Bank", "Kotak Mahindra Bank", "LIC",
        "Bajaj Finserv", "Policybazaar", "Ditto Insurance", "Acko", "Digit Insurance",
        # Telecom and electronics
        "Jio", "Airtel", "Vi", "boAt", "Noise", "Samsung", "Apple", "OnePlus",
        "Xiaomi", "Realme", "Vivo", "Oppo",
        # Auto and mobility
        "Tata Motors", "Mahindra", "Maruti Suzuki", "Hyundai", "Hero MotoCorp",
        "Bajaj Auto", "TVS Motor", "Royal Enfield", "Ola Electric", "Ather Energy",
        "Ola", "Uber", "Rapido",
        # Fashion, jewellery and footwear
        "Tanishq", "CaratLane", "Titan", "Fastrack", "FabIndia", "Manyavar", "Biba",
        "W for Woman", "Libas", "Westside", "Zudio", "Pantaloons", "Max Fashion",
        "Allen Solly", "Van Heusen", "Peter England", "Louis Philippe", "Raymond",
        "Snitch", "The Souled Store", "Bewakoof", "Nike", "Adidas", "Puma", "Bata",
        "Zara", "H&M", "Levi's", "Jockey", "Decathlon",
        # Restaurants and cafés
        "Domino's", "McDonald's", "KFC", "Pizza Hut", "Burger King", "Starbucks",
        "Chaayos", "Third Wave Coffee", "Blue Tokai",
        # Travel, media and education
        "MakeMyTrip", "OYO", "IndiGo", "Air India", "Netflix", "Amazon Prime Video",
        "JioHotstar", "Spotify", "Dream11", "BYJU'S", "Unacademy", "Physics Wallah",
    },
    key=str.lower,
)


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
  "big_idea": "one bold new creative direction in 2-3 sentences",
  "brand_profile": {
    "found": true,
    "sells": "what the company sells, one line",
    "category": "e.g. Packaged snacks",
    "positioning": "its positioning or brand promise, one line",
    "audience": "its typical target audience, one line",
    "tone": "the usual tone of its ads, a few words",
    "competitors": ["up to 4 main competitors in India"]
  },
  "history": {
    "campaigns": [
      {"year": "2024", "name": "campaign name", "idea": "core idea or tagline in one line", "score": 0}
    ],
    "verdict": "above | on_par | below | unknown",
    "why": "2 sentences comparing the new campaign with the brand's past work",
    "consistency": "one line: does it continue or break the brand's recurring themes?"
  }
}"""

HISTORY_YEARS = 4
NOT_FOUND = "BRAND_NOT_FOUND"


def history_rules(history_notes):
    if not history_notes.strip():
        return (
            "- No research on the brand was provided. Return brand_profile.found as false "
            "with the other profile fields empty, history.campaigns as [] and "
            "history.verdict as \"unknown\".\n"
        )
    return (
        "- Research notes on the brand (found with Google Search) are below. Fill "
        "brand_profile ONLY from these notes; leave a field empty if the notes say "
        "'Not found'. Never add facts from memory.\n"
        "- Use the brand profile when judging the brand_fit check, and use it to write "
        "variants that sound like this brand.\n"
        "- If the target audience was not given, use the brand's typical audience from "
        "the notes.\n"
        "- For history, use ONLY campaigns named in the notes. Never add campaigns from "
        "memory. If the notes contain no real campaigns, return history.campaigns as [] "
        "and history.verdict as \"unknown\".\n"
        "- Score each past campaign on the same strict 0-10 scale as the new one, then say "
        "whether the new campaign is above, on_par with or below the brand's usual standard.\n\n"
        f"Research notes:\n{history_notes}\n\n"
    )


def build_prompt(brand, audience, campaign, history_notes=""):
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
        "- Write for the stated audience. Keep Indian market context in mind.\n"
        + history_rules(history_notes)
        + "\nReply with JSON only, exactly in this shape:\n"
        + SCHEMA
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

    history = as_dict(data.get("history"))
    past = []
    for c in history.get("campaigns", []) if isinstance(history.get("campaigns"), list) else []:
        c = as_dict(c)
        if c.get("name"):
            past.append(
                {
                    "year": str(c.get("year", "")).strip(),
                    "name": str(c["name"]).strip(),
                    "idea": c.get("idea", ""),
                    "score": clamp(c.get("score")),
                }
            )
    past = past[:8]
    history_verdict = str(history.get("verdict", "")).strip().lower().replace(" ", "_")
    if history_verdict not in ("above", "on_par", "below") or not past:
        history_verdict = "unknown"

    profile_raw = as_dict(data.get("brand_profile"))
    profile = {k: str(profile_raw.get(k) or "").strip() for k in ("sells", "category", "positioning", "audience", "tone")}
    profile = {k: ("" if v.lower() in ("not found", "n/a", "unknown") else v) for k, v in profile.items()}
    profile["competitors"] = as_list(profile_raw.get("competitors"))[:4]
    profile["found"] = bool(profile_raw.get("found")) and any(profile[k] for k in ("sells", "positioning", "audience"))

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
        "brand_profile": profile,
        "history": {
            "campaigns": past,
            "verdict": history_verdict,
            "why": history.get("why", ""),
            "consistency": history.get("consistency", ""),
        },
    }


# Same inputs = instant answer from cache instead of a new API call.
def call_gemini(prompt, search=False):
    """Retry when Gemini is busy, then fall back to the next model.

    search=True lets Gemini use Google Search and returns plain text;
    otherwise the reply is JSON.
    """
    if search:
        config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.2,
        )
    else:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.7,
        )
    last_error = None
    for model in [MODEL_NAME, *FALLBACK_MODELS]:
        for attempt in range(3):
            try:
                return get_client().models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
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


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def research_brand(brand):
    """Find the brand's real campaigns from the last few years using Google Search."""
    this_year = datetime.date.today().year
    first_year = this_year - HISTORY_YEARS
    prompt = (
        f"Search the web for the brand '{brand}' (focus on India) and report what you find.\n\n"
        "Part 1, brand profile:\n"
        "- What the company sells and its category\n"
        "- Its positioning or brand promise\n"
        "- Its typical target audience\n"
        "- The usual tone of its advertising\n"
        "- Its main competitors in India\n\n"
        f"Part 2, up to 8 notable advertising campaigns from {first_year} to {this_year}: "
        "year, campaign name, the core idea or tagline, and one line on how it was "
        "received if the sources say.\n\n"
        "Rules: only report what you actually found in search results. Do not guess or "
        "fill gaps from memory. If a detail isn't in the results, write 'Not found'. "
        f"If you cannot find this brand at all, reply with exactly {NOT_FOUND} and nothing else."
    )
    response = call_gemini(prompt, search=True)

    sources, seen = [], set()
    suggestions_html = ""
    try:
        meta = response.candidates[0].grounding_metadata
        for chunk in meta.grounding_chunks or []:
            web = chunk.web
            if web and web.uri and web.uri not in seen:
                seen.add(web.uri)
                sources.append({"title": web.title or web.domain or "Source", "url": web.uri})
        if meta.search_entry_point and meta.search_entry_point.rendered_content:
            suggestions_html = meta.search_entry_point.rendered_content
    except (AttributeError, IndexError, TypeError):
        pass

    notes = response.text or ""
    found = bool(notes.strip()) and NOT_FOUND not in notes
    return {
        "found": found,
        "notes": notes if found else "",
        "sources": sources[:8] if found else [],
        "suggestions_html": suggestions_html,
    }


@st.cache_data(show_spinner=False, ttl=60 * 60 * 6)
def roast_campaign(brand, audience, campaign, history_notes=""):
    response = call_gemini(build_prompt(brand, audience, campaign, history_notes))
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


def history_chart(past, new_score):
    """Past campaigns in grey, the new campaign in blue, ranked by score."""
    rows = [(f"{c['year']} · {c['name']}" if c["year"] else c["name"], c["score"], False) for c in past]
    rows.append(("This campaign", new_score, True))
    rows.sort(key=lambda r: (r[1], r[2]), reverse=True)

    labels = [(r[0][:38] + "…") if len(r[0]) > 39 else r[0] for r in rows]
    fig = go.Figure(
        go.Bar(
            y=labels,
            x=[r[1] for r in rows],
            orientation="h",
            marker=dict(color=["#2a78d6" if r[2] else "#898781" for r in rows], cornerradius=4),
            text=[r[1] for r in rows],
            textposition="outside",
            customdata=[r[0] for r in rows],
            hovertemplate="%{customdata}: %{x}/10<extra></extra>",
        )
    )
    fig.update_layout(
        height=60 + 44 * len(rows),
        bargap=0.3,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(range=[0, 11], dtick=2, showgrid=True, zeroline=False, title=None),
        yaxis=dict(autorange="reversed", title=None),
        showlegend=False,
    )
    return fig


HISTORY_VERDICTS = {
    "above": ("⬆️", "Above their usual standard"),
    "on_par": ("➡️", "On par with their past work"),
    "below": ("⬇️", "Below their usual standard"),
}


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
    ]
    p = r["brand_profile"]
    if p["found"]:
        lines += [f"## About {brand}"]
        for label, key in [("What they sell", "sells"), ("Category", "category"), ("Positioning", "positioning"),
                           ("Usual audience", "audience"), ("Ad tone", "tone")]:
            if p[key]:
                lines.append(f"- {label}: {p[key]}")
        if p["competitors"]:
            lines.append(f"- Competitors: {', '.join(p['competitors'])}")
        lines.append("")
    h = r["history"]
    if h["verdict"] != "unknown":
        lines += [
            f"## Vs. {brand}'s past campaigns",
            f"**{HISTORY_VERDICTS[h['verdict']][1]}.** {h['why']}",
            f"Consistency: {h['consistency']}",
            "",
            *[f"- {c['year']} · {c['name']} ({c['score']}/10): {c['idea']}" for c in h["campaigns"]],
            "",
        ]
    lines += [
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

brand = (
    st.selectbox(
        "Brand name",
        options=BRANDS,
        index=None,
        key="brand",
        accept_new_options=True,
        placeholder="Pick from the list, or type any brand",
        help="The list has popular brands in India. Not there? Just type the name and press Enter.",
    )
    or ""
)
campaign = st.text_area(
    "Campaign copy or brief",
    key="campaign",
    height=160,
    placeholder="Paste the ad copy, caption or brief here",
)
audience = st.text_input(
    "Target audience", key="audience", placeholder="e.g. Urban millennials in Delhi aged 25-35"
)

compare = st.toggle(
    "Look up the brand online",
    value=True,
    help=f"Searches Google for the brand's profile and its campaigns from the last {HISTORY_YEARS} "
    "years, then ranks the new campaign against them. Adds about 15 seconds.",
)

if st.button("🔥 Pre-test this campaign", type="primary", width="stretch"):
    if not campaign.strip():
        st.error("Paste a campaign first, or pick one of the samples above.")
    else:
        try:
            research = None
            st.session_state["research_status"] = "off"
            if compare and brand.strip():
                with st.spinner(f"Looking up {brand.strip()} online..."):
                    try:
                        research = research_brand(brand.strip())
                        st.session_state["research_status"] = "ok" if research["found"] else "not_found"
                    except Exception as e:
                        # The pre-test still works without the lookup. Keep the reason
                        # so it can be shown on screen and found in the app logs.
                        st.session_state["research_status"] = "failed"
                        st.session_state["research_error"] = f"{type(e).__name__}: {e}"[:500]
                        print(f"Brand lookup failed for {brand!r}: {e!r}", flush=True)
            elif compare:
                st.session_state["research_status"] = "no_brand"

            with st.spinner("Checking strategy, scoring AIDA and writing variants... (takes about 20 seconds)"):
                st.session_state["result"] = roast_campaign(
                    brand.strip(),
                    audience.strip(),
                    campaign.strip(),
                    research["notes"] if research else "",
                )
                st.session_state["result_inputs"] = (brand.strip(), campaign.strip())
                st.session_state["research"] = research
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

    # 2b. Brand profile and the brand's own past campaigns
    research = st.session_state.get("research")
    research_status = st.session_state.get("research_status", "off")
    history = result["history"]
    profile = result["brand_profile"]

    if research_status != "off":
        st.markdown(f"### 🏷️ About {shown_brand or 'the brand'}")
        if research_status == "failed":
            st.caption("Couldn't search online right now. The rest of the pre-test still ran.")
            with st.expander("Why the search failed"):
                st.code(st.session_state.get("research_error", "No details recorded."), language=None)
        elif research_status == "no_brand":
            st.caption("Pick or type a brand name to look it up online.")
        elif research_status == "not_found" or not profile["found"]:
            st.warning(
                f"Couldn't find reliable information about **{shown_brand}** online. "
                "The pre-test below uses only what you entered."
            )
        else:
            with st.container(border=True):
                rows = [
                    ("What they sell", profile["sells"]),
                    ("Category", profile["category"]),
                    ("Positioning", profile["positioning"]),
                    ("Usual audience", profile["audience"]),
                    ("Ad tone", profile["tone"]),
                    ("Competitors", ", ".join(profile["competitors"])),
                ]
                st.markdown("  \n".join(f"**{label}:** {value}" for label, value in rows if value))

    if research_status == "ok" and profile["found"]:
        st.markdown(f"### 📚 Vs. {shown_brand}'s past campaigns")
        if history["verdict"] == "unknown":
            st.caption(
                f"Not enough public campaign history found for this brand in the last {HISTORY_YEARS} years, "
                "so there's nothing reliable to compare against."
            )
        else:
            icon_h, label_h = HISTORY_VERDICTS[history["verdict"]]
            ranked = sorted([c["score"] for c in history["campaigns"]] + [result["overall_score"]], reverse=True)
            rank = ranked.index(result["overall_score"]) + 1
            st.markdown(
                f"**{icon_h} {label_h}** · ranks #{rank} of {len(ranked)} against "
                f"{len(history['campaigns'])} past campaigns found"
            )
            if history["why"]:
                st.write(history["why"])
            if history["consistency"]:
                st.caption(f"Brand consistency: {history['consistency']}")
            st.plotly_chart(
                history_chart(history["campaigns"], result["overall_score"]),
                width="stretch",
                config={"displayModeBar": False},
            )
            with st.expander("Past campaigns found"):
                for c in history["campaigns"]:
                    year = f"{c['year']} · " if c["year"] else ""
                    st.markdown(f"**{year}{c['name']}** ({c['score']}/10)  \n{c['idea']}")
        if research and research["sources"]:
            st.markdown(
                "**Sources:** "
                + " · ".join(f"[{s['title']}]({s['url']})" for s in research["sources"])
            )
        if research and research["suggestions_html"]:
            # Google requires these search suggestions to be shown with search-based results.
            st.html(research["suggestions_html"])
        st.caption(
            "Brand details and past campaigns are found with Google Search and summarised "
            "by AI. Check the sources before quoting them."
        )

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
