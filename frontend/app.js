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
let historyChart = null;
let backtestChart = null;
let showPillars = false;
let historyDays = 180; // Match HTML default

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initSliders();
    checkHealth();
    refreshMAC();
    loadThresholds();
    initHistoryChart();
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
    // Convert to depletion score (1 - MAC): high = stressed, low = healthy
    const depletionScore = 1 - data.mac_score;

    // Update score value (show depletion)
    document.getElementById('macScoreValue').textContent = depletionScore.toFixed(2);
    document.getElementById('macTimestamp').textContent = formatTimestamp(data.timestamp);

    // Update interpretation (based on depletion)
    const interpEl = document.getElementById('macInterpretation');
    interpEl.textContent = getDepletionInterpretation(depletionScore);
    interpEl.className = 'interpretation ' + getDepletionClass(depletionScore);

    // Update multiplier
    document.getElementById('macMultiplier').textContent = `${data.multiplier.toFixed(2)}x`;
    document.getElementById('macTier').textContent = data.multiplier_tier;

    // Update pillars (as depletion)
    updatePillarGrid(data.pillar_scores);
    updatePillarRadar(data.pillar_scores);

    // Update alerts
    updateAlerts(data.breach_flags);

    // Update gauge (as depletion)
    updateMACGauge(depletionScore);

    // Update data status banner
    updateDataStatus(data);
}

function updateDataStatus(data) {
    const isLive = data.is_live === true;
    const sourceIcon = document.getElementById('sourceIcon');
    const sourceValue = document.getElementById('dataSource');
    const refreshValue = document.getElementById('lastRefresh');
    const refreshAgo = document.getElementById('refreshAgo');
    const indicatorCount = document.querySelector('.indicator-count');

    // Update source indicator
    if (isLive) {
        sourceIcon.className = 'source-icon live';
        sourceValue.className = 'source-value live';
        sourceValue.textContent = data.data_source || 'FRED API (Live)';
    } else {
        sourceIcon.className = 'source-icon demo';
        sourceValue.className = 'source-value demo';
        sourceValue.textContent = data.data_source || 'Demo Data';
    }

    // Update timestamp
    if (data.timestamp) {
        const timestamp = new Date(data.timestamp);
        refreshValue.textContent = timestamp.toLocaleString();
        refreshAgo.textContent = `(${getTimeAgo(timestamp)})`;
    }

    // Update indicator count
    if (data.indicators) {
        const count = Object.keys(data.indicators).length;
        indicatorCount.textContent = `${count} indicators`;
    } else {
        indicatorCount.textContent = '5 pillars';
    }
}

function getTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);

    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
}

// Depletion interpretation: high = bad, low = good
function getDepletionInterpretation(depletion) {
    if (depletion >= 0.65) return "CRITICAL - Severe stress, high contagion risk";
    if (depletion >= 0.50) return "STRETCHED - Elevated stress, reduced resilience";
    if (depletion >= 0.35) return "CAUTIOUS - Moderate stress, vigilance needed";
    return "COMFORTABLE - Low stress, markets resilient";
}

function getDepletionClass(depletion) {
    if (depletion >= 0.65) return 'breach';      // red
    if (depletion >= 0.50) return 'stretched';   // orange
    if (depletion >= 0.35) return 'thin';        // yellow
    return 'comfortable';                         // green
}

// Legacy function for backwards compatibility
function getInterpretationClass(score) {
    return getDepletionClass(1 - score);
}

function updatePillarGrid(pillars) {
    const grid = document.getElementById('pillarGrid');
    grid.innerHTML = '';

    for (const [name, data] of Object.entries(pillars)) {
        // Convert to depletion: high = stressed
        const depletion = 1 - data.score;
        const depletionStatus = getDepletionStatus(depletion);

        const item = document.createElement('div');
        item.className = `pillar-item ${depletionStatus.toLowerCase()}`;
        item.innerHTML = `
            <div class="name">${name}</div>
            <div class="score">${depletion.toFixed(2)}</div>
            <div class="status">${depletionStatus}</div>
        `;
        grid.appendChild(item);
    }
}

function getDepletionStatus(depletion) {
    if (depletion >= 0.65) return 'CRITICAL';
    if (depletion >= 0.50) return 'STRETCHED';
    if (depletion >= 0.35) return 'CAUTIOUS';
    return 'COMFORTABLE';
}

function updatePillarRadar(pillars) {
    const ctx = document.getElementById('pillarRadar');
    if (!ctx) return;

    const labels = Object.keys(pillars).map(p => p.charAt(0).toUpperCase() + p.slice(1));
    // Convert to depletion: high values spike outward = danger
    const depletions = Object.values(pillars).map(p => 1 - p.score);

    // Color based on average depletion
    const avgDepletion = depletions.reduce((a, b) => a + b, 0) / depletions.length;
    const radarColor = getDepletionColor(avgDepletion);

    if (pillarRadarChart) {
        pillarRadarChart.data.labels = labels;
        pillarRadarChart.data.datasets[0].data = depletions;
        pillarRadarChart.data.datasets[0].backgroundColor = radarColor.bg;
        pillarRadarChart.data.datasets[0].borderColor = radarColor.border;
        pillarRadarChart.data.datasets[0].pointBackgroundColor = radarColor.border;
        pillarRadarChart.update();
    } else {
        pillarRadarChart = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Pillar Stress',
                    data: depletions,
                    fill: true,
                    backgroundColor: radarColor.bg,
                    borderColor: radarColor.border,
                    pointBackgroundColor: radarColor.border,
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: radarColor.border
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

function getDepletionColor(depletion) {
    // High depletion = red (danger), low = green (safe)
    if (depletion >= 0.65) return { bg: 'rgba(239, 68, 68, 0.3)', border: '#ef4444' };   // red
    if (depletion >= 0.50) return { bg: 'rgba(249, 115, 22, 0.3)', border: '#f97316' };  // orange
    if (depletion >= 0.35) return { bg: 'rgba(251, 191, 36, 0.3)', border: '#fbbf24' };  // yellow
    return { bg: 'rgba(16, 185, 129, 0.3)', border: '#10b981' };                          // green
}

function updateMACGauge(depletion) {
    // depletion score is already passed in (1 - MAC)
    const ctx = document.getElementById('macGauge');
    if (!ctx) return;

    // High depletion = red (danger), low = green (safe)
    const getGaugeColor = (d) => {
        if (d >= 0.65) return '#ef4444';  // red - critical
        if (d >= 0.50) return '#f97316';  // orange - stretched
        if (d >= 0.35) return '#fbbf24';  // yellow - cautious
        return '#10b981';                  // green - comfortable
    };

    if (macGaugeChart) {
        macGaugeChart.data.datasets[0].data = [depletion, 1 - depletion];
        macGaugeChart.data.datasets[0].backgroundColor = [getGaugeColor(depletion), '#1f2937'];
        macGaugeChart.update();
    } else {
        macGaugeChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                datasets: [{
                    data: [depletion, 1 - depletion],
                    backgroundColor: [getGaugeColor(depletion), '#1f2937'],
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
            policy_room: { ample: 150, thin: 50, breach: 25 },
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

// History Chart
async function fetchHistoricalData(days) {
    console.log(`Fetching history for ${days} days...`);
    try {
        const response = await fetch(`${API_BASE}/mac/history?days=${days}`);
        if (response.ok) {
            const result = await response.json();
            console.log(`History loaded: ${result.count} records from ${result.source}`);
            if (result.data && result.data.length > 0) {
                console.log(`Date range: ${result.data[0].date} to ${result.data[result.data.length-1].date}`);
            }
            return result.data;
        }
    } catch (error) {
        console.error('Failed to fetch history:', error);
    }

    // Fallback to generated demo data
    console.log(`Using frontend demo data for ${days} days`);
    const demoData = generateDemoHistory(days);
    console.log(`Generated ${demoData.length} demo records, dates: ${demoData[0]?.date} to ${demoData[demoData.length-1]?.date}`);
    return demoData;
}

function generateDemoHistory(days) {
    const data = [];
    const now = new Date();

    // Define stress episodes (days ago, duration, severity)
    // Cover full range for longer time periods
    const stressEpisodes = [
        // 5-year history episodes
        { start: 1800, duration: 30, severity: 0.30 },  // Major crisis ~5 years ago
        { start: 1500, duration: 25, severity: 0.22 },  // ~4 years ago
        { start: 1200, duration: 20, severity: 0.18 },  // ~3.3 years ago
        { start: 900, duration: 35, severity: 0.35 },   // Major crisis ~2.5 years ago
        { start: 700, duration: 15, severity: 0.20 },   // ~2 years ago
        { start: 500, duration: 20, severity: 0.25 },   // ~1.4 years ago
        { start: 350, duration: 18, severity: 0.22 },   // ~1 year ago
        // Recent episodes
        { start: 150, duration: 20, severity: 0.25 },   // Major stress event
        { start: 90, duration: 10, severity: 0.15 },    // Moderate stress
        { start: 45, duration: 8, severity: 0.20 },     // Recent stress
        { start: 15, duration: 5, severity: 0.12 },     // Minor recent stress
    ];

    // Base values - start in comfortable territory
    let liquidity = 0.68;
    let valuation = 0.62;
    let positioning = 0.55;
    let volatility = 0.58;
    let policy = 0.60;

    for (let i = days; i >= 0; i--) {
        const date = new Date(now);
        date.setDate(date.getDate() - i);

        // Check if we're in a stress episode
        let stressBoost = 0;
        for (const episode of stressEpisodes) {
            if (i <= episode.start && i > episode.start - episode.duration) {
                // Ramp up stress at start, peak in middle, decay at end
                const progress = (episode.start - i) / episode.duration;
                const stressShape = Math.sin(progress * Math.PI); // Bell curve
                stressBoost = Math.max(stressBoost, episode.severity * stressShape);
            }
        }

        // Random walk with larger steps and weaker mean reversion
        const baseVol = 0.08;  // Base volatility
        const stressVol = stressBoost * 0.15;  // Extra volatility during stress

        liquidity = clamp(
            liquidity + (Math.random() - 0.5) * (baseVol + stressVol) + (0.65 - liquidity) * 0.005 - stressBoost * 0.3,
            0.15, 0.92
        );
        valuation = clamp(
            valuation + (Math.random() - 0.5) * (baseVol + stressVol) + (0.60 - valuation) * 0.005 - stressBoost * 0.25,
            0.18, 0.90
        );
        positioning = clamp(
            positioning + (Math.random() - 0.5) * (baseVol * 1.2 + stressVol) + (0.55 - positioning) * 0.005 - stressBoost * 0.35,
            0.12, 0.88
        );
        volatility = clamp(
            volatility + (Math.random() - 0.5) * (baseVol * 1.3 + stressVol) + (0.58 - volatility) * 0.008 - stressBoost * 0.40,
            0.15, 0.95
        );
        policy = clamp(
            policy + (Math.random() - 0.5) * (baseVol * 0.6) + (0.60 - policy) * 0.003,
            0.30, 0.80
        );

        // Calculate MAC as average
        const mac = (liquidity + valuation + positioning + volatility + policy) / 5;

        data.push({
            date: date.toISOString().split('T')[0],
            mac: mac,
            liquidity: liquidity,
            valuation: valuation,
            positioning: positioning,
            volatility: volatility,
            policy: policy
        });
    }

    return data;
}

function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
}

async function initHistoryChart() {
    const ctx = document.getElementById('historyChart');
    if (!ctx) return;

    const historicalData = await fetchHistoricalData(historyDays);

    // Convert to stress/depletion scores (1 - value): high = danger
    // Format labels based on time period
    const labelFormat = historyDays > 90
        ? { month: 'short', year: '2-digit' }  // "Jan '25" for longer periods
        : { month: 'short', day: 'numeric' };   // "Jan 15" for shorter periods

    const chartData = {
        labels: historicalData.map(d => {
            const date = new Date(d.date);
            return date.toLocaleDateString('en-US', labelFormat);
        }),
        datasets: [
            {
                label: 'Stress Index',
                data: historicalData.map(d => 1 - d.mac),
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                fill: true,
                tension: 0.3,
                borderWidth: 2,
            },
            {
                label: 'Liquidity Stress',
                data: historicalData.map(d => 1 - d.liquidity),
                borderColor: '#06b6d4',
                borderWidth: 1.5,
                tension: 0.3,
                hidden: true,
            },
            {
                label: 'Valuation Stress',
                data: historicalData.map(d => 1 - d.valuation),
                borderColor: '#8b5cf6',
                borderWidth: 1.5,
                tension: 0.3,
                hidden: true,
            },
            {
                label: 'Positioning Stress',
                data: historicalData.map(d => 1 - d.positioning),
                borderColor: '#f59e0b',
                borderWidth: 1.5,
                tension: 0.3,
                hidden: true,
            },
            {
                label: 'Volatility Stress',
                data: historicalData.map(d => 1 - d.volatility),
                borderColor: '#ef4444',
                borderWidth: 1.5,
                tension: 0.3,
                hidden: true,
            },
            {
                label: 'Policy Stress',
                data: historicalData.map(d => 1 - d.policy),
                borderColor: '#10b981',
                borderWidth: 1.5,
                tension: 0.3,
                hidden: true,
            }
        ]
    };

    historyChart = new Chart(ctx, {
        type: 'line',
        data: chartData,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index',
            },
            plugins: {
                legend: {
                    display: false,
                },
                tooltip: {
                    backgroundColor: '#1a2332',
                    titleColor: '#f3f4f6',
                    bodyColor: '#9ca3af',
                    borderColor: '#374151',
                    borderWidth: 1,
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ${context.raw.toFixed(3)}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: '#1f2937',
                    },
                    ticks: {
                        color: '#9ca3af',
                        maxTicksLimit: 10,
                    }
                },
                y: {
                    min: 0,
                    max: 1,
                    grid: {
                        color: '#1f2937',
                    },
                    ticks: {
                        color: '#9ca3af',
                        callback: function(value) {
                            return value.toFixed(1);
                        }
                    }
                }
            }
        }
    });
}

function togglePillarLines() {
    if (!historyChart) return;

    showPillars = !showPillars;
    const btn = document.getElementById('togglePillars');
    btn.textContent = showPillars ? 'Hide Pillars' : 'Show Pillars';
    btn.classList.toggle('active', showPillars);

    // Toggle visibility of pillar datasets (indices 1-5)
    for (let i = 1; i <= 5; i++) {
        historyChart.data.datasets[i].hidden = !showPillars;
    }

    // Update legend visibility
    const legendItems = document.querySelectorAll('.legend-item');
    legendItems.forEach((item, index) => {
        if (index > 0) {
            item.classList.toggle('hidden', !showPillars);
        }
    });

    historyChart.update();
}

async function updateHistoryRange() {
    const select = document.getElementById('historyRange');
    historyDays = parseInt(select.value);

    if (!historyChart) return;

    const historicalData = await fetchHistoricalData(historyDays);

    // Format labels based on time period
    const labelFormat = historyDays > 90
        ? { month: 'short', year: '2-digit' }  // "Jan '25" for longer periods
        : { month: 'short', day: 'numeric' };   // "Jan 15" for shorter periods

    historyChart.data.labels = historicalData.map(d => {
        const date = new Date(d.date);
        return date.toLocaleDateString('en-US', labelFormat);
    });

    // Convert to stress/depletion (1 - value)
    historyChart.data.datasets[0].data = historicalData.map(d => 1 - d.mac);
    historyChart.data.datasets[1].data = historicalData.map(d => 1 - d.liquidity);
    historyChart.data.datasets[2].data = historicalData.map(d => 1 - d.valuation);
    historyChart.data.datasets[3].data = historicalData.map(d => 1 - d.positioning);
    historyChart.data.datasets[4].data = historicalData.map(d => 1 - d.volatility);
    historyChart.data.datasets[5].data = historicalData.map(d => 1 - d.policy);

    historyChart.update();
}

// Backtest Historical Chart with Crisis Events
async function loadBacktestHistory() {
    const loadingEl = document.getElementById('backtestLoading');
    const tbody = document.getElementById('backtestTableBody');

    loadingEl.style.display = 'block';
    tbody.innerHTML = '<tr><td colspan="7" class="placeholder">Loading historical FRED data...</td></tr>';

    const interval = document.getElementById('backtestInterval').value;

    try {
        const response = await fetch(`${API_BASE}/backtest/run?start=2006-01-01&interval=${interval}`);
        if (!response.ok) throw new Error('Failed to load backtest data');

        backtestData = await response.json();

        if (backtestData.error) {
            throw new Error(backtestData.message || backtestData.error);
        }

        updateBacktestHistoryChart(backtestData);
        updateBacktestSummary(backtestData);
        updateCrisisAnalysisTable(backtestData);

    } catch (error) {
        console.error('Backtest history failed:', error);
        tbody.innerHTML = `<tr><td colspan="7" class="placeholder">Failed to load: ${error.message}</td></tr>`;
    } finally {
        loadingEl.style.display = 'none';
    }
}

function updateBacktestHistoryChart(data) {
    const ctx = document.getElementById('backtestChart');
    if (!ctx) return;

    const timeSeries = data.time_series || [];

    // Prepare data
    const labels = timeSeries.map(d => {
        const date = new Date(d.date);
        return date.toLocaleDateString('en-US', { year: '2-digit', month: 'short' });
    });

    // Convert to depletion scores: high = stressed/danger
    const depletionScores = timeSeries.map(d => 1 - d.mac_score);

    // Create background zone datasets for DEPLETION (high = danger at top)
    // Zones now use depletion thresholds:
    // COMFORTABLE: 0 to 0.35 (bottom - safe)
    // CAUTIOUS: 0.35 to 0.50
    // STRETCHED: 0.50 to 0.65
    // CRITICAL: 0.65 to 1.0 (top - danger)
    const zoneDatasets = [
        // COMFORTABLE zone: depletion 0 to 0.35 (bottom of chart - safe)
        {
            label: 'Comfortable Zone',
            data: Array(timeSeries.length).fill(0.35),
            borderColor: 'transparent',
            backgroundColor: 'rgba(16, 185, 129, 0.08)',  // green
            fill: { target: { value: 0 }, above: 'rgba(16, 185, 129, 0.08)' },
            pointRadius: 0,
            order: 4,
        },
        // CAUTIOUS zone: depletion 0.35 to 0.50
        {
            label: 'Cautious Zone',
            data: Array(timeSeries.length).fill(0.50),
            borderColor: 'transparent',
            backgroundColor: 'rgba(251, 191, 36, 0.10)',  // yellow
            fill: { target: { value: 0.35 }, above: 'rgba(251, 191, 36, 0.10)' },
            pointRadius: 0,
            order: 4,
        },
        // STRETCHED zone: depletion 0.50 to 0.65
        {
            label: 'Stretched Zone',
            data: Array(timeSeries.length).fill(0.65),
            borderColor: 'transparent',
            backgroundColor: 'rgba(249, 115, 22, 0.12)',  // orange
            fill: { target: { value: 0.50 }, above: 'rgba(249, 115, 22, 0.12)' },
            pointRadius: 0,
            order: 4,
        },
        // CRITICAL zone: depletion 0.65 to 1.0 (top of chart - danger)
        {
            label: 'Critical Zone',
            data: Array(timeSeries.length).fill(1.0),
            borderColor: 'transparent',
            backgroundColor: 'rgba(239, 68, 68, 0.15)',  // red
            fill: { target: { value: 0.65 }, above: 'rgba(239, 68, 68, 0.15)' },
            pointRadius: 0,
            order: 4,
        },
    ];

    // Main depletion score line (rendered on top)
    const datasets = [
        ...zoneDatasets,
        {
            label: 'Stress Index',
            data: depletionScores,
            borderColor: '#3b82f6',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            fill: false,
            tension: 0.3,
            borderWidth: 2,
            pointRadius: timeSeries.map(d => d.crisis_event ? 8 : 2),
            pointBackgroundColor: timeSeries.map((d, i) => {
                const depletion = depletionScores[i];
                if (d.crisis_event) return '#ef4444';
                if (depletion >= 0.65) return '#ef4444';  // critical
                if (depletion >= 0.50) return '#f97316';  // stretched
                if (depletion >= 0.35) return '#fbbf24';  // cautious
                return '#10b981';                          // comfortable
            }),
            pointBorderColor: timeSeries.map(d => d.crisis_event ? '#fff' : 'transparent'),
            pointBorderWidth: timeSeries.map(d => d.crisis_event ? 2 : 0),
            order: 1,
        }
    ];

    // Add threshold lines for depletion
    datasets.push({
        label: 'Cautious Threshold (0.35)',
        data: Array(timeSeries.length).fill(0.35),
        borderColor: 'rgba(251, 191, 36, 0.6)',
        borderWidth: 1,
        borderDash: [5, 5],
        pointRadius: 0,
        fill: false,
        order: 2,
    });

    datasets.push({
        label: 'Stretched Threshold (0.50)',
        data: Array(timeSeries.length).fill(0.50),
        borderColor: 'rgba(249, 115, 22, 0.6)',
        borderWidth: 1,
        borderDash: [5, 5],
        pointRadius: 0,
        fill: false,
        order: 2,
    });

    datasets.push({
        label: 'Critical Threshold (0.65)',
        data: Array(timeSeries.length).fill(0.65),
        borderColor: 'rgba(239, 68, 68, 0.6)',
        borderWidth: 1,
        borderDash: [5, 5],
        pointRadius: 0,
        fill: false,
        order: 2,
    });

    if (backtestChart) {
        backtestChart.destroy();
    }

    backtestChart = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index',
            },
            plugins: {
                legend: {
                    display: false,
                },
                tooltip: {
                    backgroundColor: '#1a2332',
                    titleColor: '#f3f4f6',
                    bodyColor: '#9ca3af',
                    borderColor: '#374151',
                    borderWidth: 1,
                    filter: function(tooltipItem) {
                        // Only show tooltip for Stress Index dataset (index 4, after 4 zone datasets)
                        return tooltipItem.datasetIndex === 4;
                    },
                    callbacks: {
                        title: function(context) {
                            if (context.length === 0) return '';
                            const point = timeSeries[context[0].dataIndex];
                            if (point && point.crisis_event) {
                                return `${point.date} - ${point.crisis_event.name}`;
                            }
                            return point ? point.date : '';
                        },
                        label: function(context) {
                            const point = timeSeries[context.dataIndex];
                            if (!point) return null;
                            const depletion = context.raw;
                            const status = getDepletionStatus(depletion);
                            const lines = [`Stress: ${depletion.toFixed(3)} (${status})`];
                            if (point.crisis_event) {
                                lines.push(`Event: ${point.crisis_event.description}`);
                            }
                            return lines;
                        },
                        afterBody: function(context) {
                            if (context.length === 0) return [];
                            const point = timeSeries[context[0].dataIndex];
                            if (point && point.breach_flags && point.breach_flags.length > 0) {
                                return [`Breaches: ${point.breach_flags.join(', ')}`];
                            }
                            return [];
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: '#1f2937',
                    },
                    ticks: {
                        color: '#9ca3af',
                        maxTicksLimit: 15,
                    }
                },
                y: {
                    min: 0,
                    max: 1,
                    // No reverse needed: high depletion (danger) naturally at top
                    grid: {
                        color: '#1f2937',
                    },
                    ticks: {
                        color: '#9ca3af',
                        callback: function(value) {
                            return value.toFixed(1);
                        }
                    },
                    title: {
                        display: true,
                        text: 'Stress Index (high = danger)',
                        color: '#9ca3af',
                        font: {
                            size: 11
                        }
                    }
                }
            }
        }
    });
}

function updateBacktestSummary(data) {
    const summary = data.summary || {};
    const crisisAnalysis = data.crisis_prediction_analysis || [];

    document.getElementById('btTotal').textContent = summary.data_points || '--';
    document.getElementById('btAvgLead').textContent = summary.average_lead_time_days || '--';
    document.getElementById('btAvgStretched').textContent = summary.average_days_stretched_before_event || '--';
    document.getElementById('btWarningRate').textContent = summary.warning_rate || '--%';
    document.getElementById('btPredictionAcc').textContent = summary.prediction_accuracy || '--%';
}

function updateCrisisAnalysisTable(data) {
    const tbody = document.getElementById('backtestTableBody');
    const crisisAnalysis = data.crisis_prediction_analysis || [];

    if (crisisAnalysis.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="placeholder">No crisis events in selected date range</td></tr>';
        return;
    }

    tbody.innerHTML = crisisAnalysis.map(crisis => {
        // Convert to depletion: high = danger
        const stressAtEvent = crisis.mac_at_event != null ? 1 - crisis.mac_at_event : null;
        const statusClass = stressAtEvent >= 0.65 ? 'badge-danger' :
                           stressAtEvent >= 0.50 ? 'badge-warning' : 'badge-success';

        const warningBadge = crisis.days_of_warning > 0 ?
            `<span class="badge badge-success">${crisis.days_of_warning} days</span>` :
            '<span class="badge badge-danger">None</span>';

        // Convert status to depletion terminology
        const depletionStatus = getDepletionStatus(stressAtEvent);

        return `
            <tr>
                <td><strong>${crisis.event}</strong></td>
                <td>${formatDate(crisis.event_date)}</td>
                <td><span class="badge ${statusClass}">${stressAtEvent?.toFixed(3) || 'N/A'}</span></td>
                <td>${crisis.first_warning_date ? formatDate(crisis.first_warning_date) : '-'}</td>
                <td>${warningBadge}</td>
                <td>${crisis.days_stretched > 0 ? `${crisis.days_stretched} days` : '-'}</td>
                <td><span class="badge ${statusClass}">${depletionStatus || 'N/A'}</span></td>
            </tr>
        `;
    }).join('');
}
