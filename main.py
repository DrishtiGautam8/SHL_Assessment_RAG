import streamlit as st
from analysis_engine import recommend_assessment
import json

# Session state initialization
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "current_index" not in st.session_state:
    st.session_state.current_index = 0
if "last_results" not in st.session_state:
    st.session_state.last_results = []
if "reply_round" not in st.session_state:
    st.session_state.reply_round = 0

# UI Title
st.title("SHL Assessment Recommender")
st.markdown("Ask a question to get recommended SHL assessments based on your needs.")

# User Input
user_input = st.text_input("What type of assessment are you looking for?", "")

# Submit Button
submit = st.button("Submit")

# Logic
if submit and user_input.strip():
    # Handle "More" request
    if user_input.lower().strip() in ["more", "more options", "more assessments"]:
        if st.session_state.reply_round >= 2:
            st.warning(" You've reached the maximum number of follow-ups for this query (3 total).")
        elif not st.session_state.last_results:
            st.warning(" No previous results found to continue from.")
        else:
            st.session_state.reply_round += 1
            start = st.session_state.current_index
            end = start + 10
            new_results = st.session_state.last_results[start:end]

            if not new_results:
                st.info(" No more assessments found.")
            else:
                st.session_state.current_index = end
                st.markdown("### 🔁 More Recommendations")
                for assessment in new_results:
                    with st.container():
                        st.markdown(f"**🔹 {assessment['name']}**  \n [View Assessment]({assessment['url']})")

    else:
        # New query: reset conversation context
        st.session_state.reply_round = 1
        st.session_state.current_index = 10

        st.markdown("---")
        st.markdown(f"**Your query:** _{user_input}_")

        with st.spinner(" Searching for relevant assessments..."):
            response = recommend_assessment(user_input)

        try:
            results = json.loads(response)
            if not isinstance(results, list):
                raise ValueError("Response must be a list.")
        except Exception as e:
            st.error(" Failed to parse response. Please try again.")
            st.text(response)
            results = []

        if results:
            st.session_state.last_results = results
            st.session_state.conversation_history.append({
                "query": user_input,
                "results": results[:10]
            })

            st.markdown("## Recommended Assessments")
            for assessment in results[:10]:
                with st.container():
                    st.markdown(f" {assessment['name']}  \n ({assessment['url']})")
        else:
            st.warning("No assessments found for your query.")

# Show more button
if st.session_state.last_results and st.session_state.reply_round > 0 and st.session_state.reply_round < 3:
    if st.button(" Show More Options"):
        st.session_state.reply_round += 1
        start = st.session_state.current_index
        end = start + 10
        more_results = st.session_state.last_results[start:end]

        if not more_results:
            st.info("No more assessments found.")
        else:
            st.session_state.current_index = end
            st.markdown("### More Recommendations")
            for assessment in more_results:
                with st.container():
                    st.markdown(f"{assessment['name']}**  \n [View Assessment]({assessment['url']})")

# Conversation history
with st.expander("Conversation History", expanded=False):
    for turn in st.session_state.conversation_history:
        st.markdown(f"**Query:** _{turn['query']}_")
        for res in turn['results']:
            st.markdown(f"• [{res['name']}]({res['url']})")
        st.markdown("---")
