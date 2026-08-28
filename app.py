"""
app.py

AstroMind — Streamlit entry point.

Run with:
    streamlit run app.py

Architecture:
    - st.session_state["chain"]    : AstroMindChain (one per browser session)
    - st.session_state["messages"] : List[dict]     (chat history for display)
    - ui/chat.py                   : renders chat bubbles + handles input
"""

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from orchestration.chain import AstroMindChain
from ui.chat import render_chat

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title  = "AstroMind",
    page_icon   = "🚀",
    layout      = "wide",
    initial_sidebar_state = "expanded",
)

# ── Session state initialisation ───────────────────────────────────────────────
# st.session_state persists across Streamlit re-runs for this browser tab.
# We initialise once — if the key already exists, we skip.

if "chain" not in st.session_state:
    st.session_state["chain"] = AstroMindChain(
        astronaut_id    = "astronaut-01",
        mission_context = "Lunar outpost rotation, Day 45.",
    )

if "messages" not in st.session_state:
    st.session_state["messages"] = []

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🚀 AstroMind")
    st.caption("Psychological support companion for long-duration spaceflight.")
    st.divider()

    st.markdown("**Session**")
    chain = st.session_state["chain"]
    st.text(f"ID: {chain.session_id[:16]}...")
    st.text(f"Turns: {chain.turn_count()}")

    st.divider()
    st.caption("Mood Dashboard and Alert Panel coming in Day 7.")

    # New session button
    if st.button("Start New Session", use_container_width=True):
        st.session_state["chain"].close()
        st.session_state["chain"]    = AstroMindChain(
            astronaut_id    = "astronaut-01",
            mission_context = "Lunar outpost rotation, Day 45.",
        )
        st.session_state["messages"] = []
        st.rerun()

# ── Main chat area ─────────────────────────────────────────────────────────────

st.header("AstroMind Companion", divider="gray")
st.caption("Everything you share is private and reviewed only by the behavioral health officer.")

render_chat(
    chain    = st.session_state["chain"],
    messages = st.session_state["messages"],
)