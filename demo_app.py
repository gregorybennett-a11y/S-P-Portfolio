"""
Public demo entry point — deploy THIS file as a second Streamlit app.

Same codebase as app.py, but with no login: visitors explore a showcase
portfolio and can edit it for their session only. Nothing is written to
GitHub, so this app needs NO secrets at all.
"""

import app

app.DEMO_MODE = True
app.main()
