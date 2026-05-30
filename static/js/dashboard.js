// Dashboard JavaScript
// Fetches market data, option chain, trend, chart analysis, global cues, news, trade ideas, and 8-layer checklist

let currentTradeIdea = null;

function formatNumber(num) {
    if (num === null || num === undefined) return '--';
    return num.toLocaleString('en-IN');
}

function formatPrice(num) {
    if (num === null || num === undefined) return '--';
    return num.toFixed(2);
}

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
            statusText.textContent = 'MARKET OPEN — Live option chain + 8-layer analysis active';
        } else {
            banner.className = 'market-status-banner closed';
            statusText.textContent = 'MARKET CLOSED — Pre-market 8-layer analysis active';
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

function renderChecklist(checklist, totalScore) {
    const grid = document.getElementById('checklistGrid');
    const scoreBadge = document.getElementById('checklistScore');
    
    if (!checklist || checklist.length === 0) {
        grid.innerHTML = '<div class="checklist-item">Checklist will appear after analysis...</div>';
        scoreBadge.textContent = '--';
        return;
    }

    const passed = checklist.filter(c => c.pass).length;
    scoreBadge.textContent = `${passed}/${checklist.length} Passed`;
    scoreBadge.className = 'badge ' + (passed >= 6 ? 'bullish' : passed >= 4 ? 'sideways' : 'bearish');

    let html = '';
    checklist.forEach(c => {
        const status = c.pass ? '✓' : '✕';
        const cls = c.pass ? 'pass' : 'fail';
        html += `<div class="checklist-item ${cls}">
            <span class="checklist-num">${c.step}</span>
            <span class="checklist-name">${c.name}</span>
            <span class="checklist-status">${status}</span>
            <span class="checklist-detail">${c.detail}</span>
        </div>`;
    });
    grid.innerHTML = html;
}

function renderLayer1(layer) {
    const badge = document.getElementById('layer1Badge');
    const stats = document.getElementById('layer1Stats');
    const details = document.getElementById('layer1Details');

    if (!layer || !layer.data) {
        badge.textContent = 'N/A';
        stats.innerHTML = '';
        details.innerHTML = '';
        return;
    }

    const bias = layer.direction || 'neutral';
    badge.textContent = bias.toUpperCase();
    badge.className = 'badge ' + (bias.includes('bull') ? 'bullish' : bias.includes('bear') ? 'bearish' : 'sideways');

    const daily = layer.data.daily || {};
    const tf60 = layer.data.tf_60min || {};
    const tf15 = layer.data.tf_15min || {};

    let statsHtml = `<div class="layer-stat"><span class="layer-stat-label">Daily Trend</span><span class="layer-stat-value">${daily.trend_structure?.trend?.replace('_', ' ') || 'N/A'}</span></div>`;
    statsHtml += `<div class="layer-stat"><span class="layer-stat-label">60min Trend</span><span class="layer-stat-value">${tf60.trend_structure?.trend?.replace('_', ' ') || 'N/A'}</span></div>`;
    statsHtml += `<div class="layer-stat"><span class="layer-stat-label">15min Trend</span><span class="layer-stat-value">${tf15.trend_structure?.trend?.replace('_', ' ') || 'N/A'}</span></div>`;
    statsHtml += `<div class="layer-stat"><span class="layer-stat-label">Alignment</span><span class="layer-stat-value">${layer.data.multi_timeframe_alignment?.replace('_', ' ') || 'N/A'}</span></div>`;
    statsHtml += `<div class="layer-stat"><span class="layer-stat-label">Score</span><span class="layer-stat-value">${layer.score}</span></div>`;
    stats.innerHTML = statsHtml;

    let detailsHtml = '<ul class="layer-detail-list">';
    (layer.details || []).forEach(d => {
        detailsHtml += `<li>${d}</li>`;
    });
    detailsHtml += '</ul>';
    details.innerHTML = detailsHtml;
}

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

async function fetchTradeIdea() {
    try {
        const res = await fetch('/api/trade-idea');
        const data = await res.json();
        currentTradeIdea = data;

        const badge = document.getElementById('confidenceBadge');
        badge.textContent = data.confidence_label + ' (' + data.confidence_score + ')';
        badge.className = 'badge confidence ' + data.confidence_label.toLowerCase();

        const topBadge = document.getElementById('confidenceBadgeTop');
        if (topBadge) {
            topBadge.textContent = data.confidence_score;
            topBadge.className = 'stat-value ' + (data.confidence_score >= 75 ? 'success' : data.confidence_score >= 55 ? 'warning' : 'danger');
        }

        // Render checklist
        renderChecklist(data.checklist, data.confidence_score);

        // Render Layer 1
        if (data.layers && data.layers.market_direction) {
            renderLayer1(data.layers.market_direction);
        }

        const trade = data.trade;
        if (!trade || trade.instrument_type === 'NO_TRADE') {
            document.getElementById('tradeInstrument').textContent = 'NO TRADE';
            document.getElementById('tradeDirection').textContent = '--';
            document.getElementById('tradeEntry').textContent = '--';
            document.getElementById('tradeStop').textContent = '--';
            document.getElementById('tradeTarget1').textContent = '--';
            document.getElementById('tradeTarget2').textContent = '--';
            document.getElementById('tradeQuantity').textContent = '--';
            document.getElementById('tradeRR').textContent = '--';
            document.getElementById('tradeProb').textContent = '--';
            document.getElementById('tradeExplanation').textContent = trade ? trade.explanation : 'No clear setup. At least one checklist item failed or signals conflict.';
            document.getElementById('tradeInvalidation').textContent = '';
            document.getElementById('hedgingNote').style.display = 'none';
            document.getElementById('btnSaveTrade').style.display = 'none';
            document.getElementById('orderTypeRow').style.display = 'none';
            document.getElementById('sessionRow').style.display = 'none';
        } else {
            document.getElementById('tradeInstrument').textContent = trade.instrument_type;
            document.getElementById('tradeDirection').textContent = trade.direction;
            document.getElementById('tradeEntry').textContent = formatPrice(trade.entry);
            document.getElementById('tradeStop').textContent = formatPrice(trade.stop_loss);
            document.getElementById('tradeTarget1').textContent = formatPrice(trade.target1);
            document.getElementById('tradeTarget2').textContent = trade.target2 ? formatPrice(trade.target2) : '--';
            document.getElementById('tradeQuantity').textContent = trade.quantity;
            document.getElementById('tradeRR').textContent = trade.risk_reward;
            document.getElementById('tradeProb').textContent = trade.estimated_probability;
            document.getElementById('tradeExplanation').textContent = trade.explanation;
            document.getElementById('tradeInvalidation').textContent = 'Invalidation: ' + trade.invalidation;
            
            if (trade.hedging_suggestion && trade.hedging_suggestion !== 'N/A') {
                const hedgeEl = document.getElementById('hedgingNote');
                hedgeEl.textContent = 'Hedging: ' + trade.hedging_suggestion;
                hedgeEl.style.display = 'block';
            }
            
            document.getElementById('btnSaveTrade').style.display = 'block';
            if (trade.order_type) {
                document.getElementById('orderTypeRow').style.display = 'flex';
                document.getElementById('tradeOrderType').textContent = trade.order_type;
            }
            if (trade.session) {
                document.getElementById('sessionRow').style.display = 'flex';
                document.getElementById('tradeSession').textContent = trade.session;
            }
        }

        const reasonList = document.getElementById('reasonList');
        reasonList.innerHTML = data.reasons.map(r => `<li>${r}</li>`).join('');
        if (data.reasons.length === 0) reasonList.innerHTML = '<li>No specific reasons available.</li>';

        const riskList = document.getElementById('riskList');
        riskList.innerHTML = data.risk_factors.map(r => `<li>${r}</li>`).join('');
        if (data.risk_factors.length === 0) riskList.innerHTML = '<li>No major risk factors detected.</li>';

        const invList = document.getElementById('invalidationList');
        invList.innerHTML = data.invalidation_scenarios.map(r => `<li>${r}</li>`).join('');
        if (data.invalidation_scenarios.length === 0) invList.innerHTML = '<li>None specified.</li>';

    } catch (e) {
        console.error('Trade idea error:', e);
    }
}

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

async function saveTrade() {
    if (!currentTradeIdea || !currentTradeIdea.trade || currentTradeIdea.trade.instrument_type === 'NO_TRADE') {
        alert('No active trade to save.');
        return;
    }

    const payload = {
        trade: currentTradeIdea.trade,
        confidence_score: currentTradeIdea.confidence_score,
        confidence_label: currentTradeIdea.confidence_label,
        market_trend: currentTradeIdea.market_trend,
        pcr: currentTradeIdea.pcr,
        max_pain: currentTradeIdea.max_pain,
        atm_strike: currentTradeIdea.atm_strike,
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

function refreshAll() {
    fetchMarketSummary();
    fetchTrend();
    fetchOptionChain();
    fetchChartAnalysis();
    fetchTradeIdea();
    fetchNews();
}

document.getElementById('btnSaveTrade').addEventListener('click', saveTrade);
setInterval(refreshAll, 30000);
refreshAll();
