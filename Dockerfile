FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY chainlens/ chainlens/

RUN pip install --no-cache-dir ".[dashboard]"

EXPOSE 8501

CMD ["streamlit", "run", "chainlens/dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]
