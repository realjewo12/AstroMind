"""
ui/chat.py

Streamlit chat UI components for AstroMind.

Handles:
- Rendering the full message history as st.chat_message bubbles
- Capturing user input and calling AstroMindChain.chat()
- Storing results in st.session_state
- Displaying per-message mood badge and risk indicator

Public API
----------
    from ui.chat import render_chat

    render_chat(chain, session_state_messages)
"""

from __future__ import annotations

import streamlit as st

from core.mood_engine import RiskLevel
from orchestration.chain import AstroMindChain, ChatResult


# ── Risk colour map ────────────────────────────────────────────────────────────

_RISK_COLOUR = {
    RiskLevel.LOW:    "#16a34a",   # green
    RiskLevel.MEDIUM: "#d97706",   # amber
    RiskLevel.HIGH:   "#dc2626",   # red
}

_RISK_LABEL = {
    RiskLevel.LOW:    "LOW",
    RiskLevel.MEDIUM: "MEDIUM",
    RiskLevel.HIGH:   "HIGH",
}


# ── Message history rendering ──────────────────────────────────────────────────

def render_history(messages: list) -> None:
    """
    Render all previous messages from st.session_state as chat bubbles.

    Each message dict has:
        role    : "user" | "assistant"
        content : str   (the display text)
        result  : ChatResult | None   (None for user messages)
    """
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            # Show mood badge under each AI response
            if msg["role"] == "assistant" and msg.get("result"):
                result: ChatResult = msg["result"]
                _render_mood_badge(result)


def _render_mood_badge(result: ChatResult) -> None:
    """Render a compact mood + wellness + risk badge under an AI message."""
    risk    = result.report.risk
    colour  = _RISK_COLOUR[risk]
    label   = _RISK_LABEL[risk]
    mood    = result.report.mood.capitalize()
    wellness = result.report.wellness

    st.markdown(
        f'<div style="margin-top:6px; font-size:12px; color:#57606a;">'
        f'Mood: <b>{mood}</b> &nbsp;|&nbsp; '
        f'Wellness: <b>{wellness}/100</b> &nbsp;|&nbsp; '
        f'Risk: <b style="color:{colour};">{label}</b>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # HIGH risk — show prominent warning
    if risk == RiskLevel.HIGH:
        st.error(
            "**Safety flag raised.** This message has been logged for "
            "the behavioral health officer. If you are in immediate distress, "
            "please contact the flight surgeon.",
            icon="🚨",
        )


# ── Input handler ──────────────────────────────────────────────────────────────

def handle_input(chain: AstroMindChain, messages: list) -> None:
    """
    Render the chat input box. When the user submits a message:
    1. Append the user message to history
    2. Call chain.chat() with a spinner
    3. Append the AI response to history
    4. Streamlit re-renders automatically

    Parameters
    ----------
    chain    : AstroMindChain   The active session chain
    messages : list             st.session_state["messages"] (mutated in place)
    """
    user_input = st.chat_input("How are you feeling today?")

    if user_input:
        # ── Show user message immediately ──────────────────────────────────
        messages.append({"role": "user", "content": user_input, "result": None})
        with st.chat_message("user"):
            st.markdown(user_input)

        # ── Call backend ───────────────────────────────────────────────────
        with st.chat_message("assistant"):
            with st.spinner("AstroMind is thinking..."):
                try:
                    result: ChatResult = chain.chat(user_input)
                except Exception as e:
                    err_msg = (
                        "Connection to the AI service was interrupted. "
                        "Please send your message again."
                    )
                    st.warning(err_msg)
                    # Remove the user message we already appended so
                    # the user can retry cleanly
                    messages.pop()
                    return

            # Display the AI response text
            st.markdown(result.response.response)
            _render_mood_badge(result)

        # ── Persist to session history ─────────────────────────────────────
        messages.append({
            "role":    "assistant",
            "content": result.response.response,
            "result":  result,
        })


# ── Public entry point ─────────────────────────────────────────────────────────

def render_chat(chain: AstroMindChain, messages: list) -> None:
    """
    Full chat UI: render history then handle new input.

    Call this once per Streamlit re-run from app.py.
    """
    render_history(messages)
    handle_input(chain, messages)