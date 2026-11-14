import time

import streamlit.components.v1 as components
import streamlit as st
import streamlit_hotkeys as hotkeys

from agent.agent import createRoofWattAgent

st.set_page_config(page_title = "RoofWatt", page_icon = "assets/rooftwatt_icon.png", layout = "wide")
hotkeys.activate([hotkeys.hk("scroll_bottom", "End", ctrl = True, prevent_default = True, help = "Scroll to the latest message")])

st.title("RoofWatt")
st.caption("A commercial solar analysis agent for properties in Houston and Los Angeles.")

@st.cache_resource
def loadAgent():
	return createRoofWattAgent()

def extractText(content):
	if isinstance(content, str):
		return content
	if isinstance(content, list):
		textParts = []
		for block in content:
			if isinstance(block, dict) and block.get("type") == "text":
				textParts.append(block.get("text", ""))

		return "\n".join(textParts)
	elif isinstance(content, dict):
		return "\n".join([f"{key}: {extractText(value)}" for key, value in content.items()])
	else:
		return str(content)

def scrollToBottom():
	componentKey = time.time_ns()

	jsCode = f"""
	<script>
		const componentKey = "{componentKey}";

		const scrollToBottom = () => {{
			if (window.frameElement) {{
				window.frameElement.scrollIntoView({{
					behavior: "smooth",
					block: "end"
				}});
			}}
		}};

		window.requestAnimationFrame(() => {{
			window.setTimeout(scrollToBottom, 150);
		}});
	</script>
	"""

	components.html(jsCode, height=0)

hotkeys.on_pressed("scroll_bottom", scrollToBottom)

if st.button("Scroll to latest message"):
	scrollToBottom()


if __name__ == "__main__":
	agent = loadAgent()

	if "chatMessages" not in st.session_state:
		st.session_state.chatMessages = []

	for message in st.session_state.chatMessages:
		with st.chat_message(message["role"]):
			st.markdown(message["content"])

	userPrompt = st.chat_input("Ask RoofWatt to find commercial properties")

	if userPrompt:
		st.session_state.chatMessages.append({
			"role": "user",
			"content": userPrompt
		})

		with st.chat_message("user"):
			st.markdown(userPrompt)

		scrollToBottom()

		with st.chat_message("assistant"):
			with st.spinner("Analyzing properties..."):
				try:
					result = agent.invoke({
						"messages": st.session_state.chatMessages
					})

					responseText = extractText(result["messages"][-1].content)
					st.markdown(responseText)

					st.session_state.chatMessages.append({
						"role": "assistant",
						"content": responseText
					})

					scrollToBottom()
				except Exception as error:
					st.error(f"RoofWatt could not complete the request: {error}")
					scrollToBottom()
