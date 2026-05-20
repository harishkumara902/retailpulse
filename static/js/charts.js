(() => {
  const colors = {
    pink: "#FFB2E6",
    lavender: "#F7AEF8",
    periwinkle: "#E382F9",
    violet: "#B388EB",
    purple: "#9A52FF",
    deep: "#8447FF",
    cyan: "#72DDF7",
    card: "#13132A",
    text: "#F0EEFF",
    muted: "#A89FC0",
  };
  const palette = [colors.cyan, colors.purple, colors.pink, colors.violet, colors.periwinkle, colors.deep];
  const money = (value) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value || 0);
  const api = (url) => fetch(url).then((r) => r.json());

  Chart.defaults.color = colors.muted;
  Chart.defaults.borderColor = "rgba(154,82,255,0.14)";
  Chart.defaults.font.family = "DM Sans";

  function lineGradient(ctx) {
    const gradient = ctx.chart.ctx.createLinearGradient(0, 0, 0, 320);
    gradient.addColorStop(0, "rgba(154,82,255,0.42)");
    gradient.addColorStop(1, "rgba(154,82,255,0)");
    return gradient;
  }

  function renderHeatmap(target, rows) {
    const host = document.getElementById(target);
    if (!host) return;
    host.innerHTML = "";
    rows.slice(0, 80).forEach((row) => {
      const opacity = Math.max(0.08, Number(row.retention || 0) / 100);
      const cell = document.createElement("div");
      cell.className = "heat-cell";
      cell.style.background = `rgba(132,71,255,${opacity})`;
      cell.textContent = `${row.period}m ${Math.round(row.retention || 0)}%`;
      cell.title = `${row.cohort_month}: ${row.customers} customers`;
      host.appendChild(cell);
    });
  }

  async function initDashboard() {
    const [kpi, trend, regions, returns, segments, forecast, anomalies] = await Promise.all([
      api("/api/kpi"), api("/api/revenue-trend"), api("/api/regional"), api("/api/return-rate"),
      api("/api/segment-distribution"), api("/api/forecast"), api("/api/anomalies"),
    ]);
    document.getElementById("kpiRevenue").textContent = money(kpi.total_revenue);
    document.getElementById("kpiOrders").textContent = kpi.total_orders.toLocaleString("en-IN");
    document.getElementById("kpiCustomers").textContent = kpi.active_customers.toLocaleString("en-IN");
    document.getElementById("kpiChurn").textContent = kpi.churn_risk.toLocaleString("en-IN");
    document.getElementById("kpiGrowth").textContent = `${kpi.mom_growth}% MoM | ${kpi.return_rate}% returns`;
    if (anomalies.length) {
      const banner = document.getElementById("anomalyBanner");
      banner.classList.remove("hidden");
      banner.querySelector("span").textContent = `${Math.min(anomalies.length, 3)} anomalies detected recently - View Details`;
    }
    new Chart(document.getElementById("revenueTrend"), {
      type: "line",
      data: {
        labels: trend.map((r) => r.month).concat(forecast.forecast.slice(0, 6).map((r) => r.date.slice(5))),
        datasets: [
          { label: "Revenue", data: trend.map((r) => r.revenue), borderColor: colors.periwinkle, backgroundColor: lineGradient, fill: true, tension: .35 },
          { label: "Forecast", data: Array(trend.length).fill(null).concat(forecast.forecast.slice(0, 6).map((r) => r.revenue)), borderColor: colors.cyan, borderDash: [6, 5], tension: .35 },
        ],
      },
      options: { responsive: true, plugins: { legend: { display: true } }, scales: { y: { ticks: { callback: money } } } },
    });
    new Chart(document.getElementById("regionDonut"), { type: "doughnut", data: { labels: regions.map((r) => r.region), datasets: [{ data: regions.map((r) => r.revenue), backgroundColor: palette }] }, options: { cutout: "64%" } });
    new Chart(document.getElementById("returnBar"), { type: "bar", data: { labels: returns.map((r) => r.category), datasets: [{ label: "Return rate", data: returns.map((r) => r.return_rate), backgroundColor: returns.map((r) => r.return_rate > 15 ? colors.pink : r.return_rate > 10 ? colors.violet : colors.cyan) }] } });
    const regionLabels = [...new Set(segments.map((r) => r.region))];
    const segmentLabels = ["Premium", "Regular", "Budget"];
    new Chart(document.getElementById("segmentStack"), {
      type: "bar",
      data: { labels: regionLabels, datasets: segmentLabels.map((seg, i) => ({ label: seg, backgroundColor: palette[i], data: regionLabels.map((region) => (segments.find((r) => r.region === region && r.segment === seg) || {}).customers || 0) })) },
      options: { scales: { x: { stacked: true }, y: { stacked: true } } },
    });
    document.getElementById("regenerateInsight").addEventListener("click", async () => {
      const box = document.getElementById("dailyInsight");
      box.textContent = "Generating...";
      const res = await fetch("/api/ai/generate-insight", { method: "POST" });
      const data = await res.json();
      box.textContent = data.content || data.error;
      document.getElementById("insightRemaining").textContent = `(${data.remaining ?? 0}/10 left)`;
    });
  }

  async function initCustomers() {
    const [churn, ltv, cohorts] = await Promise.all([api("/api/churn-risk"), api("/api/customer-ltv"), api("/api/cohort")]);
    const tbody = document.querySelector("#churnTable tbody");
    const drawRows = () => {
      const selected = document.getElementById("segmentFilter").value;
      tbody.innerHTML = churn.filter((r) => !selected || r.segment === selected).map((r) => `<tr><td>${r.name}</td><td>${r.segment}</td><td>${r.region}</td><td>${r.total_orders}</td><td>${Math.round(r.days_since_last_order)}</td><td><span class="badge ${r.risk_level}">${r.risk_level}</span></td></tr>`).join("");
    };
    document.getElementById("segmentFilter").addEventListener("change", drawRows);
    drawRows();
    new Chart(document.getElementById("ltvChart"), { type: "bar", data: { labels: ltv.slice(0, 10).map((r) => r.name), datasets: [{ label: "LTV", data: ltv.slice(0, 10).map((r) => r.ltv), backgroundColor: colors.deep }] }, options: { indexAxis: "y", scales: { x: { ticks: { callback: money } } } } });
    renderHeatmap("cohortHeatmap", cohorts);
  }

  async function initProducts() {
    const [products, categories, returns] = await Promise.all([api("/api/products"), api("/api/category-performance"), api("/api/return-rate")]);
    document.querySelector("#productTable tbody").innerHTML = products.map((p) => `<tr><td>${p.name}</td><td>${p.category}</td><td>${p.units_sold}</td><td>${money(p.revenue)}</td><td>${p.margin}%</td></tr>`).join("");
    new Chart(document.getElementById("categoryRadar"), { type: "radar", data: { labels: categories.map((r) => r.category), datasets: [{ label: "Revenue", data: categories.map((r) => r.revenue), borderColor: colors.periwinkle, backgroundColor: "rgba(227,130,249,0.18)" }] } });
    new Chart(document.getElementById("productReturnBar"), { type: "bar", data: { labels: returns.map((r) => r.category), datasets: [{ label: "Return rate", data: returns.map((r) => r.return_rate), backgroundColor: palette }] } });
  }

  async function initRegions() {
    const regions = await api("/api/regional");
    const map = document.getElementById("regionMap");
    map.innerHTML = regions.map((r) => `<div class="map-cell" style="grid-area:${r.region.toLowerCase()}">${r.region}<br>${money(r.revenue)}</div>`).join("");
    document.getElementById("regionCards").innerHTML = regions.map((r) => `<article class="region-card"><strong>${r.region}</strong><span>${money(r.revenue)}</span><br><small>${r.orders} orders | ${Number(r.avg_order).toFixed(0)} AOV</small></article>`).join("");
    new Chart(document.getElementById("shippingChart"), { type: "bar", data: { labels: regions.map((r) => r.region), datasets: [{ label: "Avg shipping days", data: regions.map((r) => r.avg_shipping), backgroundColor: colors.cyan }] } });
  }

  async function initCohorts() { renderHeatmap("cohortHeatmap", await api("/api/cohort")); }

  async function initAnomalies() {
    const [forecast, anomalies] = await Promise.all([api("/api/forecast"), api("/api/anomalies")]);
    document.getElementById("anomalyTimeline").innerHTML = anomalies.map((a) => `<article class="anomaly-card"><span class="badge ${a.type}">${a.type}</span><h2>${a.metric}</h2><p>${a.date} | Value ${Number(a.value).toLocaleString("en-IN")} | ${a.deviation}% from normal | ${a.severity}</p></article>`).join("");
    const hist = forecast.historical.slice(-90);
    new Chart(document.getElementById("anomalyRevenueChart"), { type: "line", data: { labels: hist.map((r) => r.date), datasets: [{ label: "Revenue", data: hist.map((r) => r.revenue), borderColor: colors.periwinkle, backgroundColor: "rgba(154,82,255,0.16)", fill: true, tension: .35 }] }, options: { scales: { y: { ticks: { callback: money } } } } });
  }

  window.RetailPulse = { initDashboard, initCustomers, initProducts, initRegions, initCohorts, initAnomalies };
})();
