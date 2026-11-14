import time
from pathlib import Path

import streamlit.components.v1 as components
import streamlit as st
import streamlit_hotkeys as hotkeys

from agent.agent import createRoofWattAgent
from agent.results import roofImages
from config import loadSettings

appRoot = Path(__file__).resolve().parent
pageIconPath = appRoot / "assets" / "Star.png"

st.set_page_config(page_title = "RoofWatt", page_icon = str(pageIconPath), layout = "wide")
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

def buildAgentHistory(messages):
	settings = loadSettings()
	remainingCharacters = settings.agentContextCharacters
	boundedHistory = []

	for message in reversed(messages[-settings.agentContextMessages:]):
		content = str(message.get("content", ""))
		if not content or remainingCharacters <= 0:
			continue

		if len(content) > remainingCharacters:
			truncationNotice = "\n[Earlier content truncated]"
			if remainingCharacters > len(truncationNotice):
				content = content[:remainingCharacters - len(truncationNotice)] + truncationNotice
			else:
				content = content[:remainingCharacters]

		boundedHistory.append({"role": message["role"], "content": content})
		remainingCharacters -= len(content)

	return list(reversed(boundedHistory))

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


def showRoofImages(images):
	for buildingId, imagePath in images:
		st.image(imagePath, caption = f"Aerial roof image, building {buildingId} (Vexcel Imaging)", width = 480)

if __name__ == "__main__":
	agent = loadAgent()

	if "chatMessages" not in st.session_state:
		st.session_state.chatMessages = []

	for message in st.session_state.chatMessages:
		with st.chat_message(message["role"]):
			st.markdown(message["content"])
			showRoofImages(message.get("images", []))

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
					history = buildAgentHistory(st.session_state.chatMessages)
					result = agent.invoke({"messages": history})

					responseText = extractText(result["messages"][-1].content)
					images = roofImages(result["messages"])
					st.markdown(responseText)
					showRoofImages(images)

					st.session_state.chatMessages.append({"role": "assistant", "content": responseText})
				except Exception as error:
					errorMessage = str(error)
					if "429" in errorMessage or "RESOURCE_EXHAUSTED" in errorMessage:
						st.error("Gemini quota is currently exhausted. Wait for the quota window to reset, then try again. RoofWatt now sends one bounded request per question.")
					else:
						st.error(f"RoofWatt could not complete the request: {errorMessage}")
					scrollToBottom()
