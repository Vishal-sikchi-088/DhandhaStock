// Dashboard JS — Modern Trading Terminal
// Fetches all APIs and renders into the redesigned DOM.

let currentTradeIdea = null;
let activeTradeId = null;

function formatNumber(num) {
    if (num === null || num === undefined) return '--';
    return num.toLocaleString('en-IN');
}

function formatPrice(num) {
    if (num === null || num === undefined) return '--';
    return num.toFixed(2);
}

function setPill(pillId, value, type) {
    const pill = document.getElementById(pillId);
    const valEl = pill.querySelector('.sp-value');
    valEl.textContent = (value || '--').toString().toUpperCase();
    pill.classList.remove('bullish', 'bearish', 'neutral');
    if (type === 'bullish') pill.classList.add('bullish');
    else if (type === 'bearish') pill.classList.add('bearish');
    else pill.classList.add('neutral');
}

function updateLastUpdated() {
    const now = new Date();
    document.getElementById('lastUpdated').textContent = now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
}

// ---- Market Summary ----

async function fetchMarketSummary() {
    try {
        const res = await fetch('/api/market-summary');
        const data = await res.json();

        document.getElementById('spotPrice').textContent = formatPrice(data.spot);
        document.getElementById('futuresPrice').textContent = formatPrice(data.futures);
        document.getElementById('vixValue').textContent = data.vix || '--';
        document.getElementById('pcrValue').textContent = data.pcr || '--';
        document.getElementById('maxPainValue').textContent = data.max_pain || '--';
        document.getElementById('dteValue').textContent = data.days_to_expiry || '--';

        const chgEl = document.getElementById('spotChange');
        chgEl.textContent = (data.change_percent >= 0 ? '+' : '') + data.change_percent + '%';
        chgEl.className = 'hero-change ' + (data.change_percent >= 0 ? 'success' : 'danger');

        const banner = document.getElementById('marketStatusBanner');
        const statusText = document.getElementById('marketStatusText');
        if (data.market_open) {
            banner.className = 'status-bar open';
            statusText.textContent = 'MARKET OPEN — Live institutional analysis';
        } else {
            banner.className = 'status-bar closed';
            statusText.textContent = 'MARKET CLOSED — Pre-market analysis active';
        }

        const chainNote = document.getElementById('chainNote');
        if (!data.market_open) {
            chainNote.textContent = 'Option chain unavailable — market closed.';
            chainNote.style.display = 'block';
        } else if (data.data_source === 'NSE_API_LIMITED') {
            chainNote.textContent = 'Option chain unavailable — NSE deprecated public API. Integrate broker API for live OI data.';
            chainNote.style.display = 'block';
        } else {
            chainNote.style.display = 'none';
        }

        updateLastUpdated();
        return data;
    } catch (e) {
        console.error('Market summary error:', e);
    }
}

// ---- Trend ----

async function fetchTrend() {
    try {
        const res = await fetch('/api/trend');
        const data = await res.json();
        const type = data.trend === 'bullish' ? 'bullish' : data.trend === 'bearish' ? 'bearish' : 'neutral';
        setPill('trendPill', data.trend, type);
    } catch (e) {
        console.error('Trend error:', e);
    }
}

// ---- Option Chain ----

async function fetchOptionChain() {
    try {
        const res = await fetch('/api/option-chain');
        const data = await res.json();
        document.getElementById('atmBadge').textContent = 'ATM: ' + data.atm_strike;

        const tbody = document.getElementById('optionTableBody');
        if (!data.market_open || !data.strikes || data.strikes.length === 0) {
            tbody.innerHTML = '<tr><td colspan="11" class="text-center">Option chain available when market is open</td></tr>';
            return;
        }
        let html = '';
        data.strikes.forEach(row => {
            let cls = row.is_atm ? 'atm' : row.is_nearby ? 'nearby' : '';
            const ceCls = row.ce_oi_change > 0 ? 'success' : 'danger';
            const peCls = row.pe_oi_change > 0 ? 'success' : 'danger';
            html += `<tr class="${cls}">
                <td>${formatNumber(row.ce_oi)}</td>
                <td class="${ceCls}">${row.ce_oi_change > 0 ? '+' : ''}${formatNumber(row.ce_oi_change)}</td>
                <td>${formatNumber(row.ce_volume)}</td>
                <td>${row.ce_iv}</td>
                <td>${row.ce_premium}</td>
                <td class="strike-col">${row.strike}</td>
                <td>${row.pe_premium}</td>
                <td>${row.pe_iv}</td>
                <td>${formatNumber(row.pe_volume)}</td>
                <td class="${peCls}">${row.pe_oi_change > 0 ? '+' : ''}${formatNumber(row.pe_oi_change)}</td>
                <td>${formatNumber(row.pe_oi)}</td>
            </tr>`;
        });
        tbody.innerHTML = html;
    } catch (e) {
        console.error('Option chain error:', e);
    }
}

// ---- Chart Analysis ----

async function fetchChartAnalysis() {
    try {
        const res = await fetch('/api/chart-analysis');
        const data = await res.json();
        if (data.error) {
            setPill('chartPill', 'N/A', 'neutral');
            document.getElementById('patternsList').innerHTML = '<div class="pattern-item">Chart data unavailable</div>';
            document.getElementById('levelsList').innerHTML = '<div class="level-item">Key levels unavailable</div>';
            return;
        }

        const bias = data.bias || 'neutral';
        const type = bias.includes('bull') ? 'bullish' : bias.includes('bear') ? 'bearish' : 'neutral';
        setPill('chartPill', bias.replace('_', ' '), type);

        document.getElementById('rsiValue').textContent = data.rsi || '--';
        document.getElementById('sma20Value').textContent = data.sma20 || '--';

        const daily = data.daily || {};
        document.getElementById('macdValue').textContent = daily.macd_bias ? daily.macd_bias.toUpperCase() : '--';

        const patternsList = document.getElementById('patternsList');
        if (data.patterns && data.patterns.length > 0) {
            patternsList.innerHTML = data.patterns.map(p => `
                <div class="pattern-item ${p.type}">
                    <span class="pattern-name">${p.pattern}</span>
                    <span class="pattern-confidence">${p.confidence}%</span>
                    <span class="pattern-desc">${p.description}</span>
                </div>
            `).join('');
        } else {
            patternsList.innerHTML = '<div class="pattern-item">No clear patterns detected.</div>';
        }

        const levelsList = document.getElementById('levelsList');
        if (data.key_levels && data.key_levels.length > 0) {
            levelsList.innerHTML = data.key_levels.map(l => `
                <div class="level-item ${l.role}">
                    <span class="level-price">${formatPrice(l.price)}</span>
                    <span class="level-type">${l.source} — ${l.role}</span>
                </div>
            `).join('');
        } else {
            levelsList.innerHTML = '<div class="level-item">No key levels identified.</div>';
        }
    } catch (e) {
        console.error('Chart analysis error:', e);
    }
}

// ---- SMC Analysis ----

async function fetchSMC() {
    try {
        const res = await fetch('/api/smc-analysis');
        const data = await res.json();
        if (data.error) {
            setPill('smcPill', 'N/A', 'neutral');
            document.getElementById('smcStructure').textContent = '--';
            document.getElementById('smcBos').textContent = '--';
            document.getElementById('smcChoch').textContent = '--';
            return;
        }

        const bias = data.bias || 'neutral';
        setPill('smcPill', bias, bias === 'bullish' ? 'bullish' : bias === 'bearish' ? 'bearish' : 'neutral');

        document.getElementById('smcStructure').textContent = (data.structure || 'N/A').replace('_', ' ');
        document.getElementById('smcBos').textContent = data.last_bos ? `${data.last_bos.direction} @ ${formatPrice(data.last_bos.level)}` : 'None';
        document.getElementById('smcChoch').textContent = data.last_choch ? `${data.last_choch.direction} @ ${formatPrice(data.last_choch.level)}` : 'None';

        const obList = document.getElementById('smcObList');
        const activeObs = (data.order_blocks || []).filter(ob => !ob.mitigated);
        if (activeObs.length > 0) {
            obList.innerHTML = activeObs.map(ob => `
                <div class="smc-item ${ob.type}">
                    <span>${ob.type.replace('_', ' ').toUpperCase()}</span>
                    <span>${formatPrice(ob.low)}-${formatPrice(ob.high)}</span>
                </div>
            `).join('');
        } else {
            obList.innerHTML = '<div class="smc-item">No active order blocks</div>';
        }

        const fvgList = document.getElementById('smcFvgList');
        if (data.fair_value_gaps && data.fair_value_gaps.length > 0) {
            fvgList.innerHTML = data.fair_value_gaps.map(fvg => `
                <div class="smc-item ${fvg.type}">
                    <span>${fvg.type.replace('_', ' ').toUpperCase()}</span>
                    <span>${formatPrice(fvg.bottom)}-${formatPrice(fvg.top)} (${fvg.gap_pct}%)</span>
                </div>
            `).join('');
        } else {
            fvgList.innerHTML = '<div class="smc-item">No unfilled FVGs</div>';
        }
    } catch (e) {
        console.error('SMC error:', e);
    }
}

// ---- VWAP & Volume Profile ----

async function fetchVWAP() {
    try {
        const res = await fetch('/api/volume-profile');
        const data = await res.json();
        if (data.error) {
            setPill('vwapPill', 'N/A', 'neutral');
            document.getElementById('vwapValue').textContent = '--';
            document.getElementById('vwapPoc').textContent = '--';
            document.getElementById('vwapVahVal').textContent = '--';
            return;
        }

        const vwap = data.vwap || {};
        const profile = data.volume_profile || {};

        document.getElementById('vwapValue').textContent = vwap.vwap || '--';
        document.getElementById('vwapPoc').textContent = profile.poc || '--';
        const vah = profile.vah || '--';
        const val = profile.val || '--';
        document.getElementById('vwapVahVal').textContent = (vah !== '--' && val !== '--') ? `${vah} / ${val}` : '--';
        setPill('vwapPill', vwap.vwap || '--', 'neutral');

        const signals = document.getElementById('vwapSignals');
        const allSignals = [];
        if (data.vwap_signals) allSignals.push(...data.vwap_signals);
        if (data.profile_signals) allSignals.push(...data.profile_signals);
        if (data.delta_signals) allSignals.push(...data.delta_signals);

        if (allSignals.length > 0) {
            signals.innerHTML = allSignals.map(s => `<div class="vwap-signal">${s}</div>`).join('');
        } else {
            signals.innerHTML = '<div class="vwap-signal">No VWAP signals</div>';
        }
    } catch (e) {
        console.error('VWAP error:', e);
    }
}

// ---- Deep OI ----

async function fetchDeepOI() {
    try {
        const res = await fetch('/api/deep-oi');
        const data = await res.json();
        if (data.error || !data.market_open) {
            const reason = data.nse_api_limited ? 'NSE API deprecated' : 'Market closed';
            setPill('oiPill', 'N/A', 'neutral');
            document.getElementById('oiBias').textContent = '--';
            document.getElementById('oiSupportWall').textContent = '--';
            document.getElementById('oiResistanceWall').textContent = '--';
            document.getElementById('oiBuildupList').innerHTML = `<div class="oi-buildup-item">${reason} — OI data unavailable</div>`;
            return;
        }

        const oiBias = data.oi_buildup ? data.oi_buildup.oi_bias : 'neutral';
        setPill('oiPill', oiBias, oiBias === 'bullish' ? 'bullish' : oiBias === 'bearish' ? 'bearish' : 'neutral');

        document.getElementById('oiBias').textContent = oiBias.toUpperCase();
        const walls = data.walls || {};
        document.getElementById('oiSupportWall').textContent = walls.support ? `${walls.support.strike}` : '--';
        document.getElementById('oiResistanceWall').textContent = walls.resistance ? `${walls.resistance.strike}` : '--';

        const buildup = data.oi_buildup || {};
        const totals = buildup.totals || {};
        document.getElementById('oiBuildupList').innerHTML = `
            <div class="oi-buildup-item"><span>CE Long Buildup</span><span class="oi-buildup-value ${totals.ce_long_buildup > 0 ? 'success' : ''}">${formatNumber(totals.ce_long_buildup)}</span></div>
            <div class="oi-buildup-item"><span>CE Short Buildup</span><span class="oi-buildup-value ${totals.ce_short_buildup > 0 ? 'danger' : ''}">${formatNumber(totals.ce_short_buildup)}</span></div>
            <div class="oi-buildup-item"><span>PE Long Buildup</span><span class="oi-buildup-value ${totals.pe_long_buildup > 0 ? 'success' : ''}">${formatNumber(totals.pe_long_buildup)}</span></div>
            <div class="oi-buildup-item"><span>PE Short Buildup</span><span class="oi-buildup-value ${totals.pe_short_buildup > 0 ? 'danger' : ''}">${formatNumber(totals.pe_short_buildup)}</span></div>
        `;
    } catch (e) {
        console.error('Deep OI error:', e);
    }
}

// ---- Institutional Flow ----

async function fetchInstitutionalFlow() {
    try {
        const res = await fetch('/api/institutional-flow');
        const data = await res.json();
        if (data.error) {
            setPill('flowPill', 'N/A', 'neutral');
            document.getElementById('fiiNet').textContent = '--';
            document.getElementById('diiNet').textContent = '--';
            document.getElementById('futuresFlow').textContent = '--';
            return;
        }

        const bias = data.cumulative_bias || 'neutral';
        const type = bias.includes('bull') ? 'bullish' : bias.includes('bear') ? 'bearish' : 'neutral';
        setPill('flowPill', bias.replace('_', ' '), type);

        const fiiDii = data.fii_dii || {};
        document.getElementById('fiiNet').textContent = fiiDii.fii_net !== undefined ? `₹${formatNumber(fiiDii.fii_net)} cr` : '--';
        document.getElementById('diiNet').textContent = fiiDii.dii_net !== undefined ? `₹${formatNumber(fiiDii.dii_net)} cr` : '--';

        const futures = data.futures || {};
        document.getElementById('futuresFlow').textContent = futures.classification ? futures.classification.replace('_', ' ').toUpperCase() : '--';

        const reasons = document.getElementById('flowReasons');
        if (data.reasons && data.reasons.length > 0) {
            reasons.innerHTML = data.reasons.map(r => `<div class="flow-reason">${r}</div>`).join('');
        } else {
            reasons.innerHTML = '<div class="flow-reason">No flow data</div>';
        }
    } catch (e) {
        console.error('Institutional flow error:', e);
    }
}

// ---- Probability Breakdown ----

function renderProbabilityBreakdown(probabilityResult) {
    const badgeTop = document.getElementById('probabilityBadgeTop');
    const barFill = document.getElementById('probabilityBarFill');
    const barLabel = document.getElementById('probabilityBarLabel');
    const grid = document.getElementById('probabilityGrid');

    if (!probabilityResult || probabilityResult.error) {
        badgeTop.textContent = '--';
        barFill.style.width = '0%';
        barLabel.textContent = '0%';
        grid.innerHTML = 'Probability data unavailable';
        document.getElementById('probStructure').textContent = '--';
        document.getElementById('probOI').textContent = '--';
        return;
    }

    const prob = probabilityResult.probability || 0;
    badgeTop.textContent = prob + '%';
    barFill.style.width = Math.min(100, prob) + '%';
    barLabel.textContent = prob + '%';

    const scores = probabilityResult.scores || {};
    const details = probabilityResult.details || {};

    document.getElementById('probStructure').textContent = Math.round(scores.market_structure || 0);
    document.getElementById('probOI').textContent = Math.round(scores.option_chain || 0);

    const labels = {
        market_structure: 'Market Structure',
        multi_timeframe: 'Multi-Timeframe',
        option_chain: 'Option Chain',
        volume_vwap: 'Volume / VWAP',
        institutional_flow: 'Institutional Flow',
        volatility: 'Volatility',
        smc_setup: 'SMC Setup',
    };

    let html = '';
    for (const [key, label] of Object.entries(labels)) {
        const score = scores[key] || 0;
        const detailList = details[key] || [];
        const detailText = detailList.length > 0 ? detailList[0] : '';
        html += `
            <div class="probability-row">
                <div class="probability-row-header">
                    <span class="probability-row-label">${label}</span>
                    <span class="probability-row-score">${Math.round(score)}/100</span>
                </div>
                <div class="probability-row-bar">
                    <div class="probability-row-fill" style="width: ${score}%"></div>
                </div>
                <div class="probability-row-detail">${detailText}</div>
            </div>
        `;
    }
    grid.innerHTML = html;
}

// ---- Trade Idea (Decision Card) ----

async function fetchTradeIdea() {
    try {
        const res = await fetch('/api/trade-idea');
        const data = await res.json();
        currentTradeIdea = data;

        const trade = data.trade;
        const isNoTrade = !trade || trade.instrument_type === 'NO_TRADE';
        const prob = data.confidence || 0;

        // Decision card styling
        const decisionCard = document.getElementById('decisionCard');
        const verdictBadge = document.getElementById('verdictBadge');
        const decisionVerdict = document.getElementById('decisionVerdict');
        const tradeBody = document.getElementById('tradeDetailsBody');
        const noTradeMsg = document.getElementById('noTradeMessage');

        // Set verdict
        let verdictClass = 'no-go';
        let verdictText = 'NO GO';
        if (prob >= 70) { verdictClass = 'go'; verdictText = 'GO'; }
        else if (prob >= 55) { verdictClass = 'marginal'; verdictText = 'MARGINAL'; }

        decisionCard.className = 'decision-card ' + verdictClass;
        verdictBadge.className = 'verdict-badge ' + verdictClass;
        verdictBadge.textContent = verdictText;

        // Header
        const biasVal = document.getElementById('marketBiasValue');
        biasVal.textContent = (data.market_bias || 'NEUTRAL').toUpperCase();
        biasVal.className = 'decision-bias ' + (data.market_bias || 'neutral').toLowerCase();
        document.getElementById('marketBiasConfidence').textContent = prob + '%';

        const gradeEl = document.getElementById('qualityGrade');
        const grade = data.trade_quality_grade || 'F';
        gradeEl.textContent = grade;
        gradeEl.className = 'decision-grade grade-' + grade;

        // Probability bar in verdict
        document.getElementById('probabilityBarFill').style.width = Math.min(100, prob) + '%';
        document.getElementById('probabilityBarLabel').textContent = prob + '%';

        if (isNoTrade) {
            tradeBody.style.display = 'none';
            noTradeMsg.style.display = 'block';
            document.getElementById('noTradeReason').textContent = data.one_line_summary || 'Edge not present. Market conditions do not meet minimum threshold.';
        } else {
            tradeBody.style.display = 'block';
            noTradeMsg.style.display = 'none';

            document.getElementById('tradeInstrument').textContent = trade.instrument_type;
            document.getElementById('tradeType').textContent = trade.trade_type;
            document.getElementById('tradeStrike').textContent = trade.strike || '--';
            document.getElementById('tradeEntry').textContent = formatPrice(trade.entry);
            document.getElementById('tradeStop').textContent = formatPrice(trade.stop_loss);
            document.getElementById('tradeTarget1').textContent = formatPrice(trade.target1);
            document.getElementById('tradeTarget2').textContent = trade.target2 ? formatPrice(trade.target2) : '--';
            document.getElementById('tradeRR').textContent = trade.risk_reward;
            document.getElementById('tradeProb').textContent = trade.estimated_probability;
            document.getElementById('tradeQuantity').textContent = trade.quantity;

            document.getElementById('summaryLine').textContent = data.one_line_summary || '';
        }

        // Probability breakdown
        if (data.probability_breakdown) {
            renderProbabilityBreakdown({
                probability: data.confidence,
                scores: data.probability_breakdown,
                details: data.layers ? {
                    market_structure: data.layers.market_structure ? data.layers.market_structure.details : [],
                    multi_timeframe: data.layers.multi_timeframe ? data.layers.multi_timeframe.details : [],
                    option_chain: data.layers.option_chain ? data.layers.option_chain.details : [],
                    volatility: data.layers.volatility ? data.layers.volatility.details : [],
                    institutional: data.layers.institutional ? data.layers.institutional.details : [],
                } : {}
            });
        }

    } catch (e) {
        console.error('Trade idea error:', e);
    }
}

// ---- Live Monitor ----

async function fetchMonitorUpdate() {
    try {
        const res = await fetch('/api/monitor-update');
        const data = await res.json();

        const panel = document.getElementById('monitorPanel');
        if (data.active_trade_count === 0) {
            panel.style.display = 'none';
            return;
        }

        panel.style.display = 'flex';
        const trades = data.trades || [];
        const first = trades[0];

        if (first) {
            activeTradeId = first.trade_id;
            document.getElementById('monitorStatus').textContent = 'ACTIVE';
            const pnlEl = document.getElementById('monitorPnl');
            pnlEl.textContent = first.current_pnl !== null ? `₹${formatNumber(first.current_pnl)}` : '--';
            pnlEl.className = 'monitor-pnl ' + (first.current_pnl > 0 ? 'success' : first.current_pnl < 0 ? 'danger' : '');
            document.getElementById('monitorAction').textContent = first.action;
            document.getElementById('monitorReason').textContent = first.reason;
        }
    } catch (e) {
        console.error('Monitor update error:', e);
    }
}

// ---- News ----

async function fetchNews() {
    try {
        const res = await fetch('/api/news');
        const news = await res.json();
        const list = document.getElementById('newsList');
        if (!news || news.length === 0) {
            list.innerHTML = 'No news available.';
            return;
        }
        // Show only first 3 headlines in the strip
        const topNews = news.slice(0, 3);
        list.innerHTML = '<ul class="news-list">' + topNews.map(n => `
            <li>
                <span class="news-sentiment ${n.sentiment}">${n.sentiment}</span>
                <span class="news-category">${n.category || 'general'}</span>
                <span>${n.title}</span>
            </li>
        `).join('') + '</ul>';
    } catch (e) {
        console.error('News error:', e);
    }
}

// ---- Actions ----

async function saveTrade() {
    if (!currentTradeIdea || !currentTradeIdea.trade || currentTradeIdea.trade.instrument_type === 'NO_TRADE') {
        alert('No active trade to save.');
        return;
    }

    const payload = {
        trade: currentTradeIdea.trade,
        confidence_score: currentTradeIdea.confidence,
        confidence_label: currentTradeIdea.confidence_label,
        market_trend: currentTradeIdea.market_bias,
        pcr: currentTradeIdea.pcr,
        max_pain: currentTradeIdea.max_pain,
        atm_strike: currentTradeIdea.strike,
        spot: currentTradeIdea.spot,
        futures: currentTradeIdea.futures,
        days_to_expiry: currentTradeIdea.days_to_expiry,
        vix: currentTradeIdea.vix,
        reasons: currentTradeIdea.reasons,
        risk_factors: currentTradeIdea.risk_factors,
        invalidation_scenarios: currentTradeIdea.invalidation_scenarios
    };

    try {
        const res = await fetch('/api/save-trade', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await res.json();
        alert(result.message);
    } catch (e) {
        console.error('Save trade error:', e);
        alert('Failed to save trade.');
    }
}

async function activateTrade() {
    if (!currentTradeIdea || !currentTradeIdea.trade || currentTradeIdea.trade.instrument_type === 'NO_TRADE') {
        alert('No active trade to monitor.');
        return;
    }

    const payload = {
        trade: currentTradeIdea.trade,
        market_bias: currentTradeIdea.market_bias,
        confidence_score: currentTradeIdea.confidence,
        trade_quality_score: currentTradeIdea.trade_quality_score,
    };

    try {
        const res = await fetch('/api/active-trades', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await res.json();
        if (result.success) {
            activeTradeId = result.trade_id;
            alert('Trade activated for live monitoring.');
            fetchMonitorUpdate();
        } else {
            alert(result.message);
        }
    } catch (e) {
        console.error('Activate trade error:', e);
        alert('Failed to activate trade.');
    }
}

async function sendMonitorAction(action) {
    if (!activeTradeId) {
        alert('No active trade.');
        return;
    }

    const reasons = {
        'EXIT': 'Manual exit triggered',
        'PARTIAL_BOOK': 'Booking partial profits',
        'TRAIL_SL': 'Trailing stop loss'
    };

    const payload = {
        trade_id: activeTradeId,
        action: action,
        reason: reasons[action] || 'Manual action'
    };

    try {
        const res = await fetch('/api/monitor-action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await res.json();
        alert(result.message);
        fetchMonitorUpdate();
    } catch (e) {
        console.error('Monitor action error:', e);
    }
}

// ---- Accordion Toggles ----

document.querySelectorAll('.ac-toggle').forEach(btn => {
    btn.addEventListener('click', function() {
        const targetId = this.dataset.target;
        const target = document.getElementById(targetId);
        if (target) {
            const isHidden = target.style.display === 'none';
            target.style.display = isHidden ? 'block' : 'none';
            this.textContent = isHidden ? '▲' : '▼';
        }
    });
});

// ---- Refresh ----

function refreshAll() {
    fetchMarketSummary();
    fetchTrend();
    fetchOptionChain();
    fetchChartAnalysis();
    fetchSMC();
    fetchVWAP();
    fetchDeepOI();
    fetchInstitutionalFlow();
    fetchTradeIdea();
    fetchMonitorUpdate();
    fetchNews();
}

// ---- Event Listeners ----

document.getElementById('btnSaveTrade').addEventListener('click', saveTrade);
document.getElementById('btnActivateTrade').addEventListener('click', activateTrade);
document.getElementById('btnPartialBook').addEventListener('click', () => sendMonitorAction('PARTIAL_BOOK'));
document.getElementById('btnTrailSl').addEventListener('click', () => sendMonitorAction('TRAIL_SL'));
document.getElementById('btnExitTrade').addEventListener('click', () => sendMonitorAction('EXIT'));

setInterval(refreshAll, 30000);
refreshAll();
