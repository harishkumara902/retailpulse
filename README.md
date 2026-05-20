# RetailPulse - E-commerce Sales Analytics Dashboard

A full-stack business intelligence platform for e-commerce analytics.

## Features
- Interactive dashboards for revenue, products, customers, regions, cohorts, and anomalies
- Advanced SQL analytics including cohort retention, customer LTV, return rates, and regional performance
- AI-powered insight generation and chatbot via Claude Haiku with session rate limits
- IQR anomaly detection, churn prediction with Logistic Regression, and 30-day revenue forecasting
- Role-based login for Admin, Manager, and Analyst users
- PDF and CSV report export
- Responsive purple-pink glassmorphism UI with Chart.js

## Tech Stack
Python Flask · SQLite · Chart.js · Claude AI Haiku · scikit-learn · ReportLab

## Demo Credentials
| Role | Username | Password |
|------|----------|----------|
| Admin | admin | admin123 |
| Manager | manager | manager123 |
| Analyst | analyst | analyst123 |

## Live Demo
[https://retailpulse.onrender.com](https://retailpulse.onrender.com)

## Setup Locally
```bash
git clone https://github.com/harishkumara902/retailpulse.git
cd retailpulse
pip install -r requirements.txt
cp .env.example .env
python data/seed_data.py
python app.py
```

Set `ANTHROPIC_API_KEY` in `.env` to enable live Claude responses. Without a key, RetailPulse uses safe local fallback text so the dashboard remains usable.

## Render Deployment
Use the included `render.yaml`, set `ANTHROPIC_API_KEY`, and deploy from the `main` branch.
