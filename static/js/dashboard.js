// Dashboard JavaScript — Institutional Trading AI
// Fetches market data, option chain, trend, chart, SMC, VWAP, Deep OI, 
// institutional flow, probability, trade ideas, and live monitoring.

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
        chgEl.className = 'stat-change ' + (data.change_percent >= 0 ? 'success' : 'danger');

        const banner = document.getElementById('marketStatusBanner');
        const statusText = document.getElementById('marketStatusText');
        if (data.market_open) {
            banner.className = 'market-status-banner open';
            statusText.textContent = 'MARKET OPEN — Live institutional analysis active';
        } else {
            banner.className = 'market-status-banner closed';
            statusText.textContent = 'MARKET CLOSED — Pre-market institutional analysis active';
        }

        const narrativePanel = document.getElementById('narrativePanel');
        const narrativeText = document.getElementById('narrativeText');
        if (!data.market_open && data.narrative && data.narrative.narrative) {
            narrativePanel.style.display = 'block';
            narrativeText.textContent = data.narrative.narrative;
        } else {
            narrativePanel.style.display = 'none';
        }

        const chainNote = document.getElementById('chainNote');
        chainNote.style.display = data.market_open ? 'none' : 'block';

        renderGlobalCues(data.premarket);
        return data;
    } catch (e) {
        console.error('Market summary error:', e);
    }
}

function renderGlobalCues(premarket) {
    const grid = document.getElementById('globalGrid');
    if (!premarket || !premarket.global_indices || premarket.global_indices.length === 0) {
        grid.innerHTML = '<div class="global-card">Global data unavailable</div>';
        return;
    }
    let html = '';
    premarket.global_indices.forEach(idx => {
        const cls = idx.change > 0 ? 'up' : idx.change < 0 ? 'down' : 'flat';
        const arrow = idx.change > 0 ? '▲' : idx.change < 0 ? '▼' : '—';
        html += `<div class="global-card ${cls}">
            <span class="global-name">${idx.name}</span>
            <span class="global-price">${formatPrice(idx.price)}</span>
            <span class="global-change">${arrow} ${Math.abs(idx.change_percent).toFixed(2)}%</span>
        </div>`;
    });
    grid.innerHTML = html;
}

// ---- Trend ----

async function fetchTrend() {
    try {
        const res = await fetch('/api/trend');
        const data = await res.json();
        const badge = document.getElementById('trendBadge');
        badge.textContent = data.trend;
        badge.className = 'badge ' + data.trend;
        document.getElementById('strengthBar').style.width = (data.strength * 10) + '%';
        document.getElementById('strengthText').textContent = 'Strength: ' + data.strength + '/10';
        document.getElementById('trendReason').textContent = data.reason;
    } catch (e) {
        console.error('Trend error:', e);
    }
}

// ---- Option Chain ----

async function fetchOptionChain() {
    try {
        const res = await fetch('/api/option-chain');
        const data = await res.json();
        document.getElementById('supportValue').textContent = formatPrice(data.support);
        document.getElementById('resistanceValue').textContent = formatPrice(data.resistance);
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
            document.getElementById('chartBiasBadge').textContent = 'N/A';
            document.getElementById('patternsList').innerHTML = '<div class="pattern-item">Chart data unavailable</div>';
            document.getElementById('levelsList').innerHTML = '<div class="level-item">Key levels unavailable</div>';
            return;
        }

        document.getElementById('rsiValue').textContent = data.rsi || '--';
        document.getElementById('sma20Value').textContent = data.sma20 || '--';
        document.getElementById('sma50Value').textContent = data.sma50 || '--';
        document.getElementById('sma200Value').textContent = data.sma200 || '--';

        const daily = data.daily || {};
        document.getElementById('macdValue').textContent = daily.macd_bias ? daily.macd_bias.toUpperCase() : '--';
        document.getElementById('atrValue').textContent = daily.atr ? daily.atr.toFixed(1) : '--';

        const biasBadge = document.getElementById('chartBiasBadge');
        biasBadge.textContent = (data.bias || 'neutral').replace('_', ' ').toUpperCase();
        biasBadge.className = 'badge ' + (data.bias && data.bias.includes('bull') ? 'bullish' : data.bias && data.bias.includes('bear') ? 'bearish' : 'sideways');

        const patternsList = document.getElementById('patternsList');
        if (data.patterns && data.patterns.length > 0) {
            patternsList.innerHTML = data.patterns.map(p => `
                <div class="pattern-item ${p.type}">
                    <span class="pattern-name">${p.pattern}</span>
                    <span class="pattern-confidence">${p.confidence}% confidence</span>
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
            document.getElementById('smcBadge').textContent = 'N/A';
            document.getElementById('smcStructure').textContent = '--';
            document.getElementById('smcBos').textContent = '--';
            document.getElementById('smcChoch').textContent = '--';
            return;
        }

        const badge = document.getElementById('smcBadge');
        badge.textContent = (data.bias || 'neutral').toUpperCase();
        badge.className = 'badge ' + (data.bias === 'bullish' ? 'bullish' : data.bias === 'bearish' ? 'bearish' : 'sideways');

        document.getElementById('smcStructure').textContent = (data.structure || 'N/A').replace('_', ' ');
        document.getElementById('smcBos').textContent = data.last_bos ? `${data.last_bos.direction} @ ${formatPrice(data.last_bos.level)}` : 'None';
        document.getElementById('smcChoch').textContent = data.last_choch ? `${data.last_choch.direction} @ ${formatPrice(data.last_choch.level)}` : 'None';

        const obList = document.getElementById('smcObList');
        const activeObs = (data.order_blocks || []).filter(ob => !ob.mitigated);
        if (activeObs.length > 0) {
            obList.innerHTML = activeObs.map(ob => `
                <div class="smc-item ${ob.type}">
                    <span class="smc-name">${ob.type.replace('_', ' ').toUpperCase()}</span>
                    <span class="smc-level">${formatPrice(ob.low)}-${formatPrice(ob.high)}</span>
                    <span class="smc-role">${ob.role}</span>
                </div>
            `).join('');
        } else {
            obList.innerHTML = '<div class="smc-item">No active order blocks</div>';
        }

        const fvgList = document.getElementById('smcFvgList');
        if (data.fair_value_gaps && data.fair_value_gaps.length > 0) {
            fvgList.innerHTML = data.fair_value_gaps.map(fvg => `
                <div class="smc-item ${fvg.type}">
                    <span class="smc-name">${fvg.type.replace('_', ' ').toUpperCase()}</span>
                    <span class="smc-level">${formatPrice(fvg.bottom)}-${formatPrice(fvg.top)}</span>
                    <span class="smc-gap">${fvg.gap_pct}%</span>
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
            document.getElementById('vwapValue').textContent = '--';
            document.getElementById('vwapDeviation').textContent = '--';
            document.getElementById('vwapPoc').textContent = '--';
            document.getElementById('vwapVah').textContent = '--';
            document.getElementById('vwapVal').textContent = '--';
            return;
        }

        const vwap = data.vwap || {};
        const profile = data.volume_profile || {};

        document.getElementById('vwapValue').textContent = vwap.vwap || '--';
        document.getElementById('vwapDeviation').textContent = vwap.deviation !== undefined ? vwap.deviation + 'σ' : '--';
        document.getElementById('vwapPoc').textContent = profile.poc || '--';
        document.getElementById('vwapVah').textContent = profile.vah || '--';
        document.getElementById('vwapVal').textContent = profile.val || '--';

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
            document.getElementById('oiBadge').textContent = 'CLOSED';
            document.getElementById('oiBias').textContent = '--';
            document.getElementById('oiSupportWall').textContent = '--';
            document.getElementById('oiResistanceWall').textContent = '--';
            document.getElementById('oiBuildupList').innerHTML = '<div class="oi-buildup-item">Market closed — OI data unavailable</div>';
            return;
        }

        const badge = document.getElementById('oiBadge');
        const oiBias = data.oi_buildup ? data.oi_buildup.oi_bias : 'neutral';
        badge.textContent = oiBias.toUpperCase();
        badge.className = 'badge ' + (oiBias === 'bullish' ? 'bullish' : oiBias === 'bearish' ? 'bearish' : 'sideways');

        document.getElementById('oiBias').textContent = oiBias.toUpperCase();
        const walls = data.walls || {};
        document.getElementById('oiSupportWall').textContent = walls.support ? `${walls.support.strike} (×${walls.support.strength_score})` : '--';
        document.getElementById('oiResistanceWall').textContent = walls.resistance ? `${walls.resistance.strike} (×${walls.resistance.strength_score})` : '--';

        const buildup = data.oi_buildup || {};
        const totals = buildup.totals || {};
        const list = document.getElementById('oiBuildupList');
        list.innerHTML = `
            <div class="oi-buildup-item">
                <span class="oi-buildup-label">CE Long Buildup</span>
                <span class="oi-buildup-value ${totals.ce_long_buildup > 0 ? 'success' : ''}">${formatNumber(totals.ce_long_buildup)}</span>
            </div>
            <div class="oi-buildup-item">
                <span class="oi-buildup-label">CE Short Buildup</span>
                <span class="oi-buildup-value ${totals.ce_short_buildup > 0 ? 'danger' : ''}">${formatNumber(totals.ce_short_buildup)}</span>
            </div>
            <div class="oi-buildup-item">
                <span class="oi-buildup-label">PE Long Buildup</span>
                <span class="oi-buildup-value ${totals.pe_long_buildup > 0 ? 'success' : ''}">${formatNumber(totals.pe_long_buildup)}</span>
            </div>
            <div class="oi-buildup-item">
                <span class="oi-buildup-label">PE Short Buildup</span>
                <span class="oi-buildup-value ${totals.pe_short_buildup > 0 ? 'danger' : ''}">${formatNumber(totals.pe_short_buildup)}</span>
            </div>
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
            document.getElementById('flowBadge').textContent = 'N/A';
            document.getElementById('fiiNet').textContent = '--';
            document.getElementById('diiNet').textContent = '--';
            document.getElementById('futuresFlow').textContent = '--';
            return;
        }

        const badge = document.getElementById('flowBadge');
        const bias = data.cumulative_bias || 'neutral';
        badge.textContent = bias.replace('_', ' ').toUpperCase();
        badge.className = 'badge ' + (bias.includes('bull') ? 'bullish' : bias.includes('bear') ? 'bearish' : 'sideways');

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
    const container = document.getElementById('probabilityPanel');
    const badge = document.getElementById('probabilityBadge');
    const barFill = document.getElementById('probabilityBarFill');
    const barLabel = document.getElementById('probabilityBarLabel');
    const grid = document.getElementById('probabilityGrid');

    if (!probabilityResult || probabilityResult.error) {
        badge.textContent = '--';
        barFill.style.width = '0%';
        barLabel.textContent = '0%';
        grid.innerHTML = 'Probability data unavailable';
        return;
    }

    const prob = probabilityResult.probability || 0;
    badge.textContent = prob + '%';
    badge.className = 'badge ' + (prob >= 70 ? 'bullish' : prob >= 50 ? 'sideways' : 'bearish');
    barFill.style.width = Math.min(100, prob) + '%';
    barLabel.textContent = prob + '%';
    barFill.className = 'probability-bar-fill ' + (prob >= 70 ? 'high' : prob >= 50 ? 'medium' : 'low');

    const scores = probabilityResult.scores || {};
    const details = probabilityResult.details || {};

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

    // Update top bar probability
    const topBadge = document.getElementById('probabilityBadgeTop');
    if (topBadge) {
        topBadge.textContent = prob;
        topBadge.className = 'stat-value ' + (prob >= 75 ? 'success' : prob >= 55 ? 'warning' : 'danger');
    }
}

// ---- Trade Idea (Institutional Format) ----

async function fetchTradeIdea() {
    try {
        const res = await fetch('/api/trade-idea');
        const data = await res.json();
        currentTradeIdea = data;

        const trade = data.trade;
        const isNoTrade = !trade || trade.instrument_type === 'NO_TRADE';

        // Market Bias
        document.getElementById('marketBiasValue').textContent = data.market_bias || 'NEUTRAL';
        document.getElementById('marketBiasValue').className = 'bias-value ' + (data.market_bias || 'neutral').toLowerCase();
        document.getElementById('marketBiasConfidence').textContent = (data.confidence || 0) + '%';

        // Trade sections visibility
        const tradeSections = ['bestTradeSection', 'tradeReasoningSection', 'riskAssessmentSection', 'qualitySection', 'tradeActions'];
        const noTradeMsg = document.getElementById('noTradeMessage');

        if (isNoTrade) {
            tradeSections.forEach(id => document.getElementById(id).style.display = 'none');
            noTradeMsg.style.display = 'block';
            document.getElementById('noTradeReason').textContent = data.one_line_summary || 'Edge not present';
            document.getElementById('confidenceBadge').textContent = data.confidence_label || 'Very Low';
            document.getElementById('confidenceBadge').className = 'badge confidence low';
        } else {
            tradeSections.forEach(id => document.getElementById(id).style.display = 'block');
            noTradeMsg.style.display = 'none';

            // Best Trade Grid
            document.getElementById('tradeInstrument').textContent = trade.instrument_type;
            document.getElementById('tradeType').textContent = trade.trade_type;
            document.getElementById('tradeStrike').textContent = trade.strike || '--';
            document.getElementById('tradeExpiry').textContent = trade.expiry || '--';
            document.getElementById('tradeEntry').textContent = formatPrice(trade.entry);
            document.getElementById('tradeStop').textContent = formatPrice(trade.stop_loss);
            document.getElementById('tradeTarget1').textContent = formatPrice(trade.target1);
            document.getElementById('tradeTarget2').textContent = trade.target2 ? formatPrice(trade.target2) : '--';
            document.getElementById('tradeTarget3').textContent = trade.target3 ? formatPrice(trade.target3) : '--';
            document.getElementById('tradeRR').textContent = trade.risk_reward;
            document.getElementById('tradeHolding').textContent = trade.expected_holding_time;
            document.getElementById('tradeProb').textContent = trade.estimated_probability;
            document.getElementById('tradeQuantity').textContent = trade.quantity;

            // Confidence badge
            const badge = document.getElementById('confidenceBadge');
            badge.textContent = data.confidence_label + ' (' + data.confidence + ')';
            badge.className = 'badge confidence ' + data.confidence_label.toLowerCase().replace(' ', '_');

            // Trade Reasoning
            const reasoningList = document.getElementById('reasoningList');
            reasoningList.innerHTML = `
                <div class="reasoning-item"><strong>Trend:</strong> ${data.trend_analysis || 'N/A'}</div>
                <div class="reasoning-item"><strong>Option Chain:</strong> ${data.option_chain_confirmation || 'N/A'}</div>
                <div class="reasoning-item"><strong>Volume/VWAP:</strong> ${data.volume_confirmation || 'N/A'}</div>
                <div class="reasoning-item"><strong>Institutional:</strong> ${data.institutional_confirmation || 'N/A'}</div>
            `;

            // Risk Assessment
            document.getElementById('riskLevel').textContent = data.risk_level || 'Medium';
            document.getElementById('riskLevel').className = 'risk-value ' + (data.risk_level || 'medium').toLowerCase();
            document.getElementById('riskInvalidation').textContent = formatPrice(data.invalidation_level) || '--';
            document.getElementById('riskPosition').textContent = data.position_size_recommendation || '--';

            // Quality Score
            const qualityScore = document.getElementById('qualityScore');
            const qualityGrade = document.getElementById('qualityGrade');
            qualityScore.textContent = (data.trade_quality_score || 0) + '/100';
            qualityGrade.textContent = data.trade_quality_grade || 'F';
            qualityGrade.className = 'quality-grade grade-' + (data.trade_quality_grade || 'F');

            document.getElementById('summaryLine').textContent = data.one_line_summary || '';
        }

        // Reasons & Risk lists
        const reasonList = document.getElementById('reasonList');
        reasonList.innerHTML = (data.reasons || []).map(r => `<li>${r}</li>`).join('');
        if ((data.reasons || []).length === 0) reasonList.innerHTML = '<li>No specific reasons available.</li>';

        const riskList = document.getElementById('riskList');
        riskList.innerHTML = (data.risk_factors || []).map(r => `<li>${r}</li>`).join('');
        if ((data.risk_factors || []).length === 0) riskList.innerHTML = '<li>No major risk factors detected.</li>';

        const invList = document.getElementById('invalidationList');
        invList.innerHTML = (data.invalidation_scenarios || []).map(r => `<li>${r}</li>`).join('');
        if ((data.invalidation_scenarios || []).length === 0) invList.innerHTML = '<li>None specified.</li>';

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

        panel.style.display = 'block';
        const trades = data.trades || [];
        const first = trades[0]; // Show first active trade

        if (first) {
            activeTradeId = first.trade_id;
            document.getElementById('monitorBadge').textContent = first.action;
            document.getElementById('monitorBadge').className = 'badge ' + 
                (first.action === 'EXIT' ? 'bearish' : first.action === 'HOLD' ? 'bullish' : 'sideways');
            document.getElementById('monitorStatus').textContent = 'ACTIVE';
            document.getElementById('monitorPnl').textContent = first.current_pnl !== null ? `₹${formatNumber(first.current_pnl)}` : '--';
            document.getElementById('monitorPnl').className = 'monitor-stat-value ' + 
                (first.current_pnl > 0 ? 'success' : first.current_pnl < 0 ? 'danger' : '');
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
        list.innerHTML = news.map(n => `
            <li>
                <span class="news-sentiment ${n.sentiment}">${n.sentiment}</span>
                <span class="news-category">${n.category || 'general'}</span>
                <span>${n.title}</span>
            </li>
        `).join('');
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
