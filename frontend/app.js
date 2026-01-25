/**
 * GRRI-MAC Framework Dashboard
 * Frontend JavaScript Application
 */

// API Configuration
const API_BASE = '/api';  // Azure SWA routes to /api automatically

// State
let macData = null;
let backtestData = null;
let thresholdsData = null;
let pillarRadarChart = null;
let macGaugeChart = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initSliders();
    checkHealth();
    refreshMAC();
    loadThresholds();
});

// Navigation
function initNavigation() {
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = link.getAttribute('href').substring(1);
            showSection(targetId);
        });
    });
}

function showSection(sectionId) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));

    document.getElementById(sectionId)?.classList.add('active');
    document.querySelector(`.nav-link[href="#${sectionId}"]`)?.classList.add('active');
}

// Sliders
function initSliders() {
    const shockSlider = document.getElementById('shockMagnitude');
    const grriSlider = document.getElementById('grriModifier');
    const macSlider = document.getElementById('macOverride');

    if (shockSlider) {
        shockSlider.addEventListener('input', () => {
            document.getElementById('shockValue').textContent = `${parseFloat(shockSlider.value).toFixed(1)}x`;
        });
    }

    if (grriSlider) {
        grriSlider.addEventListener('input', () => {
            document.getElementById('grriValue').textContent = `${parseFloat(grriSlider.value).toFixed(2)}x`;
        });
    }

    if (macSlider) {
        macSlider.addEventListener('input', () => {
            document.getElementById('macOverrideValue').textContent = parseFloat(macSlider.value).toFixed(2);
        });
    }
}

// API Functions
async function checkHealth() {
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.querySelector('.status-text');

    try {
        const response = await fetch(`${API_BASE}/health`);
        if (response.ok) {
            statusDot.classList.add('connected');
            statusDot.classList.remove('error');
            statusText.textContent = 'Connected';
        } else {
            throw new Error('API not healthy');
        }
    } catch (error) {
        statusDot.classList.add('error');
        statusDot.classList.remove('connected');
        statusText.textContent = 'Disconnected';
        console.error('Health check failed:', error);
    }
}

async function refreshMAC() {
    try {
        const response = await fetch(`${API_BASE}/mac/demo`);
        if (!response.ok) throw new Error('Failed to fetch MAC data');

        macData = await response.json();
        updateMACDisplay(macData);
    } catch (error) {
        console.error('Failed to refresh MAC:', error);
        // Show demo data if API fails
        const demoData = {
            mac_score: 0.59,
            interpretation: "THIN - Limited buffer, elevated transmission risk",
            multiplier: 1.8,
            multiplier_tier: "Elevated",
            pillar_scores: {
                liquidity: { score: 0.72, status: "THIN" },
                valuation: { score: 0.58, status: "THIN" },
                positioning: { score: 0.45, status: "THIN" },
                volatility: { score: 0.65, status: "THIN" },
                policy: { score: 0.55, status: "THIN" }
            },
            breach_flags: [],
            is_demo: true,
            timestamp: new Date().toISOString()
        };
        updateMACDisplay(demoData);
    }
}

function updateMACDisplay(data) {
    // Update score value
    document.getElementById('macScoreValue').textContent = data.mac_score.toFixed(2);
    document.getElementById('macTimestamp').textContent = formatTimestamp(data.timestamp);

    // Update interpretation
    const interpEl = document.getElementById('macInterpretation');
    interpEl.textContent = data.interpretation;
    interpEl.className = 'interpretation ' + getInterpretationClass(data.mac_score);

    // Update multiplier
    document.getElementById('macMultiplier').textContent = `${data.multiplier.toFixed(2)}x`;
    document.getElementById('macTier').textContent = data.multiplier_tier;

    // Update pillars
    updatePillarGrid(data.pillar_scores);
    updatePillarRadar(data.pillar_scores);

    // Update alerts
    updateAlerts(data.breach_flags);

    // Update gauge
    updateMACGauge(data.mac_score);
}

function getInterpretationClass(score) {
    if (score >= 0.8) return 'ample';
    if (score >= 0.6) return 'comfortable';
    if (score >= 0.4) return 'thin';
    if (score >= 0.2) return 'stretched';
    return 'breach';
}

function updatePillarGrid(pillars) {
    const grid = document.getElementById('pillarGrid');
    grid.innerHTML = '';

    for (const [name, data] of Object.entries(pillars)) {
        const item = document.createElement('div');
        item.className = `pillar-item ${data.status.toLowerCase()}`;
        item.innerHTML = `
            <div class="name">${name}</div>
            <div class="score">${data.score.toFixed(2)}</div>
            <div class="status">${data.status}</div>
        `;
        grid.appendChild(item);
    }
}

function updatePillarRadar(pillars) {
    const ctx = document.getElementById('pillarRadar');
    if (!ctx) return;

    const labels = Object.keys(pillars).map(p => p.charAt(0).toUpperCase() + p.slice(1));
    const scores = Object.values(pillars).map(p => p.score);

    if (pillarRadarChart) {
        pillarRadarChart.data.labels = labels;
        pillarRadarChart.data.datasets[0].data = scores;
        pillarRadarChart.update();
    } else {
        pillarRadarChart = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Pillar Scores',
                    data: scores,
                    fill: true,
                    backgroundColor: 'rgba(59, 130, 246, 0.2)',
                    borderColor: 'rgb(59, 130, 246)',
                    pointBackgroundColor: 'rgb(59, 130, 246)',
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: 'rgb(59, 130, 246)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 1,
                        ticks: {
                            stepSize: 0.2,
                            color: '#9ca3af'
                        },
                        grid: {
                            color: '#374151'
                        },
                        angleLines: {
                            color: '#374151'
                        },
                        pointLabels: {
                            color: '#f3f4f6',
                            font: {
                                size: 12
                            }
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }
}

function updateMACGauge(score) {
    const ctx = document.getElementById('macGauge');
    if (!ctx) return;

    const getColor = (s) => {
        if (s >= 0.8) return '#10b981';
        if (s >= 0.6) return '#34d399';
        if (s >= 0.4) return '#fbbf24';
        if (s >= 0.2) return '#f97316';
        return '#ef4444';
    };

    if (macGaugeChart) {
        macGaugeChart.data.datasets[0].data = [score, 1 - score];
        macGaugeChart.data.datasets[0].backgroundColor = [getColor(score), '#1f2937'];
        macGaugeChart.update();
    } else {
        macGaugeChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                datasets: [{
                    data: [score, 1 - score],
                    backgroundColor: [getColor(score), '#1f2937'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                circumference: 180,
                rotation: -90,
                cutout: '75%',
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        enabled: false
                    }
                }
            }
        });
    }
}

function updateAlerts(breachFlags) {
    const alertsList = document.getElementById('alertsList');

    if (!breachFlags || breachFlags.length === 0) {
        alertsList.innerHTML = '<div class="alert-placeholder">No active breaches</div>';
        return;
    }

    alertsList.innerHTML = breachFlags.map(flag => `
        <div class="alert-item">
            <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                <path d="M8.982 1.566a1.13 1.13 0 0 0-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767L8.982 1.566zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 5.995A.905.905 0 0 1 8 5zm.002 6a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"/>
            </svg>
            <span>${flag.toUpperCase()} pillar breaching threshold</span>
        </div>
    `).join('');
}

// Backtest Functions
async function runBacktest() {
    const tbody = document.getElementById('backtestTableBody');
    tbody.innerHTML = '<tr><td colspan="8" class="placeholder">Running backtest...</td></tr>';

    try {
        const response = await fetch(`${API_BASE}/backtest/run`);
        if (!response.ok) throw new Error('Backtest failed');

        backtestData = await response.json();
        updateBacktestDisplay(backtestData);
    } catch (error) {
        console.error('Backtest failed:', error);
        tbody.innerHTML = '<tr><td colspan="8" class="placeholder">Failed to run backtest. Using demo data.</td></tr>';

        // Show demo backtest data
        const demoBacktest = getDemoBacktestData();
        updateBacktestDisplay(demoBacktest);
    }
}

function getDemoBacktestData() {
    return {
        summary: {
            total_scenarios: 6,
            passed: 5,
            failed: 1,
            mac_range_accuracy: 83.3,
            breach_accuracy: 100,
            hedge_prediction_accuracy: 83.3
        },
        results: [
            { scenario_name: "Pre-COVID (Jan 2020)", scenario_date: "2020-01-15", mac_score: 0.78, multiplier: 1.1, breach_flags: [], treasury_hedge_worked: true, hedge_prediction_correct: true, key_insight: "Treasury hedge worked - buffers held" },
            { scenario_name: "COVID Peak (Mar 2020)", scenario_date: "2020-03-16", mac_score: 0.12, multiplier: 5.0, breach_flags: ["liquidity", "positioning", "volatility"], treasury_hedge_worked: false, hedge_prediction_correct: true, key_insight: "CORRECT: Positioning breach predicted hedge failure" },
            { scenario_name: "Post-COVID (Jun 2020)", scenario_date: "2020-06-15", mac_score: 0.58, multiplier: 1.8, breach_flags: [], treasury_hedge_worked: true, hedge_prediction_correct: true, key_insight: "Treasury hedge worked - buffers held" },
            { scenario_name: "2022 Rate Hikes", scenario_date: "2022-09-15", mac_score: 0.42, multiplier: 2.2, breach_flags: ["policy"], treasury_hedge_worked: true, hedge_prediction_correct: true, key_insight: "Treasury hedge worked - buffers held" },
            { scenario_name: "SVB Crisis (Mar 2023)", scenario_date: "2023-03-10", mac_score: 0.35, multiplier: 2.5, breach_flags: ["liquidity"], treasury_hedge_worked: true, hedge_prediction_correct: true, key_insight: "Treasury hedge worked - buffers held" },
            { scenario_name: "April 2025 Crisis", scenario_date: "2025-04-07", mac_score: 0.18, multiplier: 4.5, breach_flags: ["positioning", "volatility"], treasury_hedge_worked: false, hedge_prediction_correct: true, key_insight: "CORRECT: Positioning breach predicted hedge failure" }
        ]
    };
}

function updateBacktestDisplay(data) {
    // Update summary
    document.getElementById('btTotal').textContent = data.summary.total_scenarios;
    document.getElementById('btPassed').textContent = data.summary.passed;
    document.getElementById('btMacAccuracy').textContent = `${data.summary.mac_range_accuracy}%`;
    document.getElementById('btBreachAccuracy').textContent = `${data.summary.breach_accuracy}%`;
    document.getElementById('btHedgeAccuracy').textContent = `${data.summary.hedge_prediction_accuracy}%`;

    // Update table
    const tbody = document.getElementById('backtestTableBody');
    tbody.innerHTML = data.results.map(r => `
        <tr>
            <td>${r.scenario_name}</td>
            <td>${formatDate(r.scenario_date)}</td>
            <td><strong>${r.mac_score.toFixed(2)}</strong></td>
            <td>${r.multiplier.toFixed(1)}x</td>
            <td>${r.breach_flags.length > 0 ? r.breach_flags.map(b => `<span class="badge badge-danger">${b}</span>`).join(' ') : '<span class="badge badge-success">None</span>'}</td>
            <td>${r.treasury_hedge_worked ? '<span class="badge badge-success">Yes</span>' : '<span class="badge badge-danger">No</span>'}</td>
            <td>${r.hedge_prediction_correct ? '<span class="badge badge-success">Correct</span>' : '<span class="badge badge-warning">Miss</span>'}</td>
            <td style="max-width: 200px; font-size: 0.8rem;">${r.key_insight}</td>
        </tr>
    `).join('');
}

// Simulator
async function runSimulation() {
    const shock = parseFloat(document.getElementById('shockMagnitude').value);
    const grri = parseFloat(document.getElementById('grriModifier').value);
    const mac = parseFloat(document.getElementById('macOverride').value);

    try {
        const response = await fetch(`${API_BASE}/simulate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                shock_magnitude: shock,
                grri_modifier: grri,
                mac_score: mac
            })
        });

        if (!response.ok) throw new Error('Simulation failed');

        const result = await response.json();
        updateSimulationDisplay(result);
    } catch (error) {
        console.error('Simulation failed:', error);
        // Calculate locally as fallback
        const macMult = getMACMultiplier(mac);
        const impact = shock * grri * macMult;
        updateSimulationDisplay({
            shock_magnitude: shock,
            grri_modifier: grri,
            mac_score: mac,
            mac_multiplier: macMult,
            market_impact: impact,
            risk_tier: getRiskTier(mac)
        });
    }
}

function getMACMultiplier(score) {
    if (score >= 0.8) return 1.0;
    if (score >= 0.6) return 1.5;
    if (score >= 0.4) return 2.0;
    if (score >= 0.2) return 3.0;
    return 5.0;
}

function getRiskTier(score) {
    if (score >= 0.8) return "Minimal";
    if (score >= 0.6) return "Low";
    if (score >= 0.4) return "Elevated";
    if (score >= 0.2) return "High";
    return "Critical";
}

function updateSimulationDisplay(result) {
    document.getElementById('eqShock').textContent = `${result.shock_magnitude.toFixed(1)}x`;
    document.getElementById('eqGrri').textContent = `${result.grri_modifier.toFixed(2)}x`;
    document.getElementById('eqMac').textContent = `${result.mac_multiplier.toFixed(1)}x`;
    document.getElementById('impactValue').textContent = result.market_impact.toFixed(2) + 'x';

    const tierEl = document.getElementById('riskTier');
    tierEl.querySelector('.tier-value').textContent = result.risk_tier;
}

// Thresholds
async function loadThresholds() {
    try {
        const response = await fetch(`${API_BASE}/thresholds`);
        if (!response.ok) throw new Error('Failed to load thresholds');

        thresholdsData = await response.json();
        updateThresholdsDisplay(thresholdsData);
    } catch (error) {
        console.error('Failed to load thresholds:', error);
        // Use fallback data
        const fallback = getDemoThresholds();
        updateThresholdsDisplay(fallback);
    }
}

function getDemoThresholds() {
    return {
        liquidity: {
            sofr_iorb: { ample: 2, thin: 8, breach: 15 },
            cp_treasury: { ample: 15, thin: 40, breach: 80 },
            cross_currency: { ample: -15, thin: -35, breach: -60 },
            bid_ask: { ample: 0.5, thin: 1.5, breach: 4.0 }
        },
        valuation: {
            term_premium: { ample: 100, thin: 25, breach: -50 },
            ig_oas: { ample: 150, thin: 90, breach: 60 },
            hy_oas: { ample: 500, thin: 350, breach: 250 }
        },
        positioning: {
            basis_trade: { ample: 300, thin: 550, breach: 750 },
            svxy_aum: { ample: 350, thin: 600, breach: 850 }
        },
        volatility: {
            vix_level: { ample_low: 12, ample_high: 18, thin_low: 8, thin_high: 28, breach_low: 0, breach_high: 40 }
        },
        policy: {
            fed_funds_vs_neutral: { ample: 25, thin: 100, breach: 200 },
            balance_sheet_gdp: { ample: 20, thin: 30, breach: 38 }
        }
    };
}

function updateThresholdsDisplay(data) {
    const grid = document.getElementById('thresholdsGrid');
    grid.innerHTML = '';

    for (const [pillar, thresholds] of Object.entries(data)) {
        const card = document.createElement('div');
        card.className = 'threshold-card';

        let tableRows = '';
        for (const [indicator, values] of Object.entries(thresholds)) {
            const formattedName = indicator.replace(/_/g, ' ');
            const valueStr = Object.entries(values)
                .map(([k, v]) => `${k}: ${v}`)
                .join(', ');
            tableRows += `<tr><td>${formattedName}</td><td>${valueStr}</td></tr>`;
        }

        card.innerHTML = `
            <h3>${pillar}</h3>
            <table class="threshold-table">
                ${tableRows}
            </table>
        `;
        grid.appendChild(card);
    }
}

// Utilities
function formatTimestamp(ts) {
    if (!ts) return '--';
    const date = new Date(ts);
    return date.toLocaleString();
}

function formatDate(dateStr) {
    if (!dateStr) return '--';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}
