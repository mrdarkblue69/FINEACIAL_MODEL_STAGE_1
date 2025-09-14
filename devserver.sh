#!/bin/bash
source .venv/bin/activate
streamlit run app.py --server.port $PORT --server.headless true --browser.serverAddress 0.0.0.0 --browser.gatherUsageStats false
