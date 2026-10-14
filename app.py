import streamlit as st
import google.generativeai as genai

st.set_page_config(
    page_title="Campaign Roaster AI",
    page_icon="🔥",
    layout="centered"
)

st.title("🔥 Campaign Roaster AI")
st.subheader("Paste any brand campaign. Get brutal marketing feedback + a rewrite.")
st.caption("Built by Vanshika Nagvani | github.com/vanshika-nagvani")

st.divider()

brand = st.text_input(
    "Brand Name",
    placeholder="e.g. Blinkit, Zepto, BellaVita"
)

campaign = st.text_area(
    "Paste your campaign copy or brief here",
    height=200,
    placeholder="e.g. Blinkit's Diwali campaign: 'Gifts delivered in 10 minutes. Because love shouldn't wait.'"
)

target_audience = st.text_input(
    "Target Audience",
    placeholder="e.g. Urban millennials in Delhi aged 25-35"
)

if st.button("🔥 Roast & Rewrite", type="primary"):
    if not campaign:
        st.error("Please paste a campaign to analyse")
    else:
        with st.spinner("Analysing campaign..."):
            try:
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                model = genai.GenerativeModel("gemini-3.8-flash")
                prompt = f"""You are a sharp senior marketing strategist with 15 years experience at top MNCs in India.

Analyse this campaign using marketing frameworks and give structured feedback.

Brand: {brand}
Target Audience: {target_audience}
Campaign Copy: {campaign}

Give your response in exactly this format:

## 🎯 Campaign Score: X/10

## 📊 Framework Analysis

**AIDA Score:**
- Attention: X/10 — [one line explanation]
- Interest: X/10 — [one line explanation]
- Desire: X/10 — [one line explanation]
- Action: X/10 — [one line explanation]

**What's Working:**
[2-3 specific things done well]

**What's Weak:**
[2-3 specific problems with the campaign]

**Emotional Pull: X/10**
[One line on emotional resonance]

**CTA Strength: X/10**
[One line on call to action effectiveness]

## 🔥 The Roast
[2-3 sentences of sharp, witty but professional critique]

## ✨ Rewritten Campaign
[Rewrite the campaign copy, making it stronger. Keep the brand voice but fix the weaknesses.]

## 💡 One Big Idea
[One bold creative direction they haven't tried yet]"""

                response = model.generate_content(prompt)
                st.markdown(response.text)
            except Exception as e:
                st.error(f"Error: {str(e)}")

st.divider()
st.caption("⚠️ This tool uses AI analysis frameworks. Results are for learning purposes.")
