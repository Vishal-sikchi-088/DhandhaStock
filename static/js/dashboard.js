// DhandhaStock Dashboard — Intraday Trading Tips Platform
// Primary signal: /api/intraday-signal  (premium-based, Groww-ready)

let currentSignal = null;
let activeTradeId = null;
const LOT_SIZE = 75;

// ── Utilities ──────────────────────────────────────────────────────────────

function fmt(n, decimals = 2) {
    if (n === null || n === undefined) return '--';
    return Number(n).toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtInt(n) {
    if (n === null || n === undefined) return '--';
    return Math.round(n).toLocaleString('en-IN');
}

function fmtRs(n) {
    if (n === null || n === undefined) return '₹--';
    return '₹' + Math.round(n).toLocaleString('en-IN');
}

function biasClass(b) {
    if (!b) return 'neutral';
    b = b.toLowerCase();
    if (b.includes('bull')) return 'bullish';
    if (b.includes('bear')) return 'bearish';
    return 'neutral';
}

function setPill(id, text, cls) {
    const el = document.getElementById(id);
    if (!el) return;
    const v = el.querySelector('.sp-value');
    if (v) v.textContent = (text || '--').toUpperCase();
    el.classList.remove('bullish', 'bearish', 'neutral');
    el.classList.add(cls || 'neutral');
}

function setEl(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text ?? '--';
}

function setClass(id, cls) {
    const el = document.getElementById(id);
    if (el) { el.className = el.className.replace(/\b(bullish|bearish|neutral|amber|success|danger)\b/g, ''); el.classList.add(cls); }
}

function now() {
    return new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
}

// ── Panel toggles ──────────────────────────────────────────────────────────

window.togglePanel = function (bodyId, headerEl) {
    const body = document.getElementById(bodyId);
    if (!body) return;
    const isHidden = body.style.display === 'none';
    body.style.display = isHidden ? 'block' : 'none';
    const btn = headerEl ? headerEl.querySelector('.panel-toggle, .ac-toggle') : null;
    if (btn) btn.textContent = isHidden ? '▲' : '▼';
};

window.toggleGroww = function () {
    const el = document.getElementById('growwSteps');
    const btn = document.getElementById('growwToggle');
    if (!el) return;
    const hidden = el.style.display === 'none';
    el.style.display = hidden ? 'block' : 'none';
    if (btn) btn.textContent = hidden ? 'How to execute on Groww ▲' : 'How to execute on Groww ▼';
};

// ── Intraday Signal (PRIMARY) ──────────────────────────────────────────────

async function fetchIntradaySignal() {
    try {
        const res = await fetch('/api/intraday-signal');
        const data = await res.json();
        currentSignal = data;
        renderSignal(data);
        if (data.morning_brief) renderMorningBrief(data.morning_brief);
        if (data.gap_info) renderGap(data.gap_info);
        if (data.orb) renderOrb(data.orb);
        setEl('lastUpdated', now());
    } catch (e) {
        console.error('Signal fetch error:', e);
    }
}

function renderSignal(d) {
    const tradeSection = document.getElementById('tradeSection');
    const noTradeSection = document.getElementById('noTradeSection');

    // Session info
    const si = d.session_info || {};
    setEl('sessionPhase', si.phase || '--');
    if (si.time_to_exit && si.time_to_exit !== 'PAST EXIT TIME') {
        setEl('timeToExit', 'Exit in ' + si.time_to_exit);
    }
    setEl('signalTime', si.time || '--');

    // VIX on stats
    if (d.vix !== null && d.vix !== undefined) {
        setEl('vixValue', d.vix.toFixed(1));
        const vixEl = document.getElementById('vixVerdict');
        if (vixEl) {
            if (d.vix <= 18) { vixEl.textContent = 'Ideal for options'; vixEl.className = 'stat-sub success'; }
            else if (d.vix <= 25) { vixEl.textContent = 'Elevated'; vixEl.className = 'stat-sub amber'; }
            else { vixEl.textContent = 'High risk!'; vixEl.className = 'stat-sub danger'; }
        }
    }

    // DTE
    if (d.dte !== null && d.dte !== undefined) {
        setEl('dteValue', d.dte);
    }

    // Event banner
    const evRisk = d.event_risk || {};
    const evBanner = document.getElementById('eventBanner');
    if (evRisk.has_events) {
        evBanner.style.display = 'flex';
        setEl('eventBannerText', evRisk.summary || evRisk.primary_event || '');
        evBanner.className = 'event-banner ' + (evRisk.should_avoid ? 'critical' : 'warning');
    } else {
        evBanner.style.display = 'none';
    }

    const card = document.getElementById('actionCard');

    if (d.has_signal && d.trade) {
        // ── SHOW TRADE ──
        const t = d.trade;
        card.className = 'action-card has-signal ' + (d.bias || 'neutral').replace('_', '-');
        tradeSection.style.display = 'block';
        noTradeSection.style.display = 'none';

        // Bias bar
        const bb = document.getElementById('biasBanner');
        const bias = (d.bias || 'neutral');
        bb.className = 'ac-bias-bar ' + biasClass(bias);
        setEl('biasBannerText', bias.replace(/_/g, ' ').toUpperCase() + ' — ' + (d.confidence || 0) + '% confidence');
        const fill = document.getElementById('confBarFill');
        if (fill) fill.style.width = Math.min(100, d.confidence || 0) + '%';
        setEl('confPct', (d.confidence || 0) + '%');

        // Grade & signal type
        setEl('actionGrade', d.grade || '--');
        document.getElementById('actionGrade').className = 'ac-grade grade-' + (d.grade || 'F');
        setEl('signalType', (d.signal_type || '').replace(/_/g, ' '));
        setEl('actionDte', d.dte + ' DTE');

        // Instrument
        const verb = t.direction === 'bearish' ? 'BUY PUT' : 'BUY CALL';
        const verbEl = document.getElementById('tradeVerb');
        verbEl.textContent = verb;
        verbEl.className = 'ac-action-verb ' + t.direction;
        setEl('tradeInstrumentName', `NIFTY ${t.strike} ${t.option_type}`);
        setEl('tradeExpiry', t.expiry_display || '--');

        // Levels
        setEl('entryRange', `₹${t.entry_low} – ₹${t.entry_high}`);
        setEl('slPremium', fmtRs(t.stop_loss));
        setEl('t1Premium', fmtRs(t.target1));
        setEl('t2Premium', fmtRs(t.target2));

        // Risk bar
        setEl('tradeQty', `${t.units} units (${t.lots} lot${t.lots > 1 ? 's' : ''})`);
        setEl('tradeLoss', fmtRs(t.total_risk));
        setEl('tradeRR', t.rr_t1 || '--');
        setEl('exitBy', '12:30 PM');

        // Why list
        const whyList = document.getElementById('whyList');
        if (d.reasons && d.reasons.length) {
            const icon = t.direction === 'bearish' ? '🔻' : '🔺';
            whyList.innerHTML = d.reasons.map(r => `<div class="why-item">${icon} ${r}</div>`).join('');
        } else {
            whyList.innerHTML = '<div class="why-item">No specific reasons available</div>';
        }

        // Risk flags
        const rfsec = document.getElementById('riskFlagsSection');
        const rfList = document.getElementById('riskFlagsList');
        if (d.risk_flags && d.risk_flags.length) {
            rfsec.style.display = 'block';
            rfList.innerHTML = d.risk_flags.map(f => `<div class="rf-item">⚠ ${f}</div>`).join('');
        } else {
            rfsec.style.display = 'none';
        }

        // Groww steps
        const steps = t.groww_steps || [];
        const ol = document.getElementById('growwStepsList');
        if (ol) ol.innerHTML = steps.map((s, i) => {
            if (s.startsWith('─')) return `<li class="groww-divider">${s}</li>`;
            return `<li>${s}</li>`;
        }).join('');

    } else {
        // ── NO TRADE ──
        card.className = 'action-card no-signal';
        tradeSection.style.display = 'none';
        noTradeSection.style.display = 'block';

        const icons = { 'EVENT_RISK': '🚫', 'EXPIRY_DAY': '⚠', 'MARKET_CLOSED': '🕐', 'TIME_BASED': '⏰', 'LOW_CONFIDENCE': '📊', 'WATCH': '👁', 'WEAK_SIGNAL': '⚡', 'PRE_OPEN': '🌅' };
        const cat = d.no_trade_category || '';
        setEl('ntIcon', icons[cat] || '⏳');
        setEl('ntTitle', cat === 'WATCH' ? 'WATCHING' : cat === 'MARKET_CLOSED' ? 'MARKET CLOSED' : cat === 'EVENT_RISK' ? 'SKIP TODAY' : 'WAIT');
        setEl('ntReason', d.no_trade_reason || 'Analysing...');

        // Bias bar (still show bias even without trade)
        const bb = document.getElementById('biasBanner');
        const bias = d.bias || 'neutral';
        bb.className = 'ac-bias-bar ' + biasClass(bias) + ' dim';
        if (bias !== 'neutral') {
            const conf = d.confidence || 0;
            setEl('biasBannerText', bias.replace(/_/g, ' ').toUpperCase() + ' (' + conf.toFixed(0) + '%) — ' + (d.no_trade_category === 'WATCH' ? 'wait for entry window' : 'insufficient edge'));
        } else {
            setEl('biasBannerText', 'NEUTRAL — no clear direction');
        }

        // No-trade reasons
        const ntWhyList = document.getElementById('noTradeWhyList');
        if (d.reasons && d.reasons.length) {
            ntWhyList.innerHTML = d.reasons.slice(0, 4).map(r => `<div class="why-item neutral">• ${r}</div>`).join('');
        } else {
            ntWhyList.innerHTML = '';
        }

        // Pending signal preview
        const pendPrev = document.getElementById('pendingPreview');
        const pendContent = document.getElementById('pendingContent');
        if (d.pending_trade && d.pending_signal) {
            pendPrev.style.display = 'block';
            const pt = d.pending_trade;
            pendContent.innerHTML = `
                <span class="pending-pill ${pt.direction}">
                    NIFTY ${pt.strike} ${pt.option_type} — Entry ₹${pt.entry_ideal}
                    | SL ₹${pt.stop_loss} | T1 ₹${pt.target1} | ${pt.rr_t1}
                </span>`;
        } else {
            pendPrev.style.display = 'none';
        }
    }
}

// ── Morning Brief ──────────────────────────────────────────────────────────

function renderMorningBrief(mb) {
    setEl('morningBiasBadge', mb.morning_bias || '--');
    document.getElementById('morningBiasBadge').className = 'morning-bias-badge ' + biasClass(mb.morning_bias || '');

    const gc = mb.global_cues || {};
    setEl('mbUsMarkets', 'US: ' + (gc.us_markets || '--'));
    const usCls = gc.us_sentiment === 'positive' ? 'success' : gc.us_sentiment === 'negative' ? 'danger' : '';
    if (usCls) { const el = document.getElementById('mbUsMarkets'); if (el) el.classList.add(usCls); }
    setEl('mbAsianMarkets', 'Asia: ' + (gc.asian_markets || '--'));
    if (gc.gold && gc.gold.price) setEl('mbGold', `Gold: $${gc.gold.price} (${gc.gold.chg_pct >= 0 ? '+' : ''}${(gc.gold.chg_pct || 0).toFixed(1)}%)`);
    if (gc.crude && gc.crude.price) setEl('mbCrude', `Crude: $${gc.crude.price} (${gc.crude.chg_pct >= 0 ? '+' : ''}${(gc.crude.chg_pct || 0).toFixed(1)}%)`);

    const va = mb.vix_assessment || {};
    setEl('mbVixVerdict', va.verdict || '--');
    document.getElementById('mbVixVerdict').className = 'mb-verdict ' + (va.color || 'neutral');

    const fd = mb.fii_dii || {};
    setEl('mbFiiVerdict', fd.verdict || '--');
    document.getElementById('mbFiiVerdict').className = 'mb-verdict ' + (fd.color || 'neutral');
    setEl('mbFiiLine', `FII: ${fd.fii_net > 0 ? '+' : ''}${fmtInt(fd.fii_net)} Cr | DII: ${fd.dii_net > 0 ? '+' : ''}${fmtInt(fd.dii_net)} Cr`);

    const kl = mb.key_levels || {};
    const sups = (kl.supports || []).map(p => p.toFixed(0)).join(', ');
    const res = (kl.resistances || []).map(p => p.toFixed(0)).join(', ');
    setEl('mbSupports', 'Support: ' + (sups || '--'));
    setEl('mbResistances', 'Resistance: ' + (res || '--'));

    // Scenarios
    const sc = mb.scenarios || {};
    const scDiv = document.getElementById('morningScenarios');
    if (scDiv && sc.bull_case) {
        scDiv.innerHTML = `
            <div class="scenario bull-case"><span class="sc-label">Bull</span> ${sc.bull_case}</div>
            <div class="scenario bear-case"><span class="sc-label">Bear</span> ${sc.bear_case}</div>
            <div class="scenario range-case"><span class="sc-label">Range</span> ${sc.range_case}</div>
        `;
    }

    // Tip
    const tipEl = document.getElementById('morningTip');
    if (tipEl && mb.strategy_suggestion) {
        tipEl.textContent = '💡 ' + mb.strategy_suggestion;
        tipEl.className = 'morning-tip ' + (mb.strategy_suggestion.startsWith('⚠') ? 'warning' : '');
    }

    // FII on stats card
    setEl('fiiNetStat', (fd.fii_net > 0 ? '+' : '') + fmtInt(fd.fii_net) + ' Cr');
    const fiiStatEl = document.getElementById('fiiNetStat');
    if (fiiStatEl) fiiStatEl.className = 'stat-value ' + (fd.fii_net > 0 ? 'success' : fd.fii_net < 0 ? 'danger' : '');
    setEl('fiiVerdict', fd.color === 'green' ? 'Bullish' : fd.color === 'red' ? 'Bearish' : 'Neutral');
}

function renderGap(gap) {
    const pts = gap.gap_pts || 0;
    setEl('gapValue', (pts >= 0 ? '+' : '') + pts.toFixed(0) + ' pts');
    const el = document.getElementById('gapValue');
    if (el) el.className = 'stat-value ' + (pts > 0 ? 'success' : pts < 0 ? 'danger' : '');
    setEl('gapType', (gap.type || 'flat').replace(/_/g, ' '));
}

function renderOrb(orb) {
    if (!orb.available) {
        setPill('orbPill', 'N/A', 'neutral');
        return;
    }
    if (orb.breakout_confirmed) {
        setPill('orbPill', orb.breakout_direction === 'bullish' ? '↑ BREAK' : '↓ BREAK',
                 orb.breakout_direction === 'bullish' ? 'bullish' : 'bearish');
    } else if (orb.inside_orb) {
        setPill('orbPill', 'INSIDE', 'neutral');
    } else {
        setPill('orbPill', 'WATCH', 'neutral');
    }
}

// ── Market Summary ─────────────────────────────────────────────────────────

async function fetchMarketSummary() {
    try {
        const res = await fetch('/api/market-summary');
        const d = await res.json();
        setEl('spotPrice', fmt(d.spot));
        setEl('pcrValue', d.pcr || '--');
        setEl('maxPainStat', 'MP: ' + (d.max_pain || '--'));
        setEl('dteValue', d.days_to_expiry || '--');
        if (d.expiry_date) setEl('expiryDate', d.expiry_date);

        const chgEl = document.getElementById('spotChange');
        if (chgEl && d.change_percent !== undefined) {
            chgEl.textContent = (d.change_percent >= 0 ? '+' : '') + d.change_percent + '%';
            chgEl.className = 'stat-change ' + (d.change_percent >= 0 ? 'success' : 'danger');
        }

        const banner = document.getElementById('marketStatusBanner');
        const statusText = document.getElementById('marketStatusText');
        if (d.market_open) {
            banner.className = 'status-bar open';
            statusText.textContent = 'MARKET OPEN — Live intraday analysis';
        } else {
            banner.className = 'status-bar closed';
            statusText.textContent = 'MARKET CLOSED — Pre-market analysis';
        }
    } catch (e) { console.error('Market summary error:', e); }
}

// ── Option Chain ───────────────────────────────────────────────────────────

async function fetchOptionChain() {
    try {
        const res = await fetch('/api/option-chain');
        const data = await res.json();
        setEl('atmBadge', 'ATM: ' + (data.atm_strike || '--'));

        const tbody = document.getElementById('optionTableBody');
        const chainNote = document.getElementById('chainNote');
        if (!data.strikes || data.strikes.length === 0) {
            tbody.innerHTML = '<tr><td colspan="11" class="text-center">Option chain available when market is open</td></tr>';
            chainNote.textContent = data.market_open ? 'NSE API limited — showing synthetic chain' : 'Market closed — synthetic chain shown below market open';
            chainNote.style.display = 'block';
            return;
        }
        chainNote.style.display = 'none';
        let html = '';
        data.strikes.forEach(row => {
            const cls = row.is_atm ? 'atm' : row.is_nearby ? 'nearby' : '';
            const ceCls = row.ce_oi_change > 0 ? 'success' : 'danger';
            const peCls = row.pe_oi_change > 0 ? 'success' : 'danger';
            html += `<tr class="${cls}">
                <td>${fmtInt(row.ce_oi)}</td>
                <td class="${ceCls}">${row.ce_oi_change > 0 ? '+' : ''}${fmtInt(row.ce_oi_change)}</td>
                <td>${fmtInt(row.ce_volume)}</td>
                <td>${row.ce_iv || '--'}</td>
                <td>${row.ce_premium || '--'}</td>
                <td class="strike-col">${row.strike}</td>
                <td>${row.pe_premium || '--'}</td>
                <td>${row.pe_iv || '--'}</td>
                <td>${fmtInt(row.pe_volume)}</td>
                <td class="${peCls}">${row.pe_oi_change > 0 ? '+' : ''}${fmtInt(row.pe_oi_change)}</td>
                <td>${fmtInt(row.pe_oi)}</td>
            </tr>`;
        });
        tbody.innerHTML = html;
    } catch (e) { console.error('Option chain error:', e); }
}

// ── Chart Analysis ─────────────────────────────────────────────────────────

async function fetchChartAnalysis() {
    try {
        const res = await fetch('/api/chart-analysis');
        const d = await res.json();

        if (d.error) {
            setPill('chartPill', 'N/A', 'neutral');
            setEl('dailyTrend', 'Daily: N/A');
            setEl('rsiValue', 'RSI: --');
            setEl('tfDaily', 'No data'); setEl('tf60m', '--'); setEl('tf15m', '--'); setEl('tf5m', '--');
            document.getElementById('levelsList').innerHTML = '<div class="level-item">Historical data loading...</div>';
            document.getElementById('patternsList').innerHTML = '<div class="pattern-item">--</div>';
            return;
        }

        const bias = d.bias || 'neutral';
        setPill('chartPill', bias.replace(/_/g, ' '), biasClass(bias));

        const daily = d.daily || {};
        const dailyTrend = (daily.trend_structure || {}).trend || '--';
        const rsi = daily.rsi ? daily.rsi.toFixed(1) : '--';
        setEl('dailyTrend', 'Daily: ' + dailyTrend);
        setEl('rsiValue', 'RSI: ' + rsi);
        setEl('tfDaily', dailyTrend);
        setEl('tf60m', ((d.tf_60min || {}).trend_structure || {}).trend || '--');
        setEl('tf15m', ((d.tf_15min || {}).trend_structure || {}).trend || '--');
        setEl('tf5m', ((d.tf_5min || {}).trend_structure || {}).trend || '--');

        const levelsList = document.getElementById('levelsList');
        if (d.key_levels && d.key_levels.length) {
            levelsList.innerHTML = d.key_levels.slice(0, 8).map(l =>
                `<div class="level-item ${l.role || ''}">
                    <span class="level-price">${fmt(l.price, 0)}</span>
                    <span class="level-type">${l.source || ''} · ${l.role || ''}</span>
                </div>`
            ).join('');
        } else {
            levelsList.innerHTML = '<div class="level-item">No key levels found</div>';
        }

        const patternsList = document.getElementById('patternsList');
        if (d.patterns && d.patterns.length) {
            patternsList.innerHTML = d.patterns.map(p =>
                `<div class="pattern-item ${p.type || ''}">
                    <span>${p.pattern}</span> <span class="pattern-confidence">${p.confidence}%</span>
                    <span class="pattern-desc">${p.description || ''}</span>
                </div>`
            ).join('');
        } else {
            patternsList.innerHTML = '<div class="pattern-item">No clear patterns detected</div>';
        }
    } catch (e) {
        console.error('Chart error:', e);
        setPill('chartPill', 'ERR', 'neutral');
    }
}

// ── SMC Analysis ───────────────────────────────────────────────────────────

async function fetchSMC() {
    try {
        const res = await fetch('/api/smc-analysis');
        const d = await res.json();

        if (d.error) {
            setPill('smcPill', 'N/A', 'neutral');
            setEl('smcStructure', 'No data');
            setEl('smcBos', '--'); setEl('smcChoch', '--');
            document.getElementById('smcObList').innerHTML = '<div class="smc-item">Insufficient 5m data</div>';
            document.getElementById('smcFvgList').innerHTML = '<div class="smc-item">--</div>';
            return;
        }

        const bias = d.bias || 'neutral';
        setPill('smcPill', bias, biasClass(bias));
        setEl('smcStructure', (d.structure || 'ranging').replace(/_/g, ' ').toUpperCase());
        setEl('smcBos', d.last_bos ? `${d.last_bos.direction.toUpperCase()} @ ${fmt(d.last_bos.level, 0)}` : 'None detected');
        setEl('smcChoch', d.last_choch ? `${d.last_choch.direction.toUpperCase()} @ ${fmt(d.last_choch.level, 0)}` : 'None detected');

        const activeObs = (d.order_blocks || []).filter(ob => !ob.mitigated);
        document.getElementById('smcObList').innerHTML = activeObs.length
            ? activeObs.map(ob => `<div class="smc-item ${ob.type || ''}">${(ob.type || '').replace(/_/g, ' ').toUpperCase()} · ${fmt(ob.low, 0)}–${fmt(ob.high, 0)}</div>`).join('')
            : '<div class="smc-item neutral">No active order blocks</div>';

        const fvgs = d.fair_value_gaps || [];
        document.getElementById('smcFvgList').innerHTML = fvgs.length
            ? fvgs.map(f => `<div class="smc-item ${f.type || ''}">${(f.type || '').replace(/_/g, ' ').toUpperCase()} · ${fmt(f.bottom, 0)}–${fmt(f.top, 0)} (${f.gap_pct}%)</div>`).join('')
            : '<div class="smc-item neutral">No unfilled FVGs</div>';
    } catch (e) {
        console.error('SMC error:', e);
        setEl('smcStructure', 'Error');
    }
}

// ── Institutional Flow ─────────────────────────────────────────────────────

async function fetchInstitutionalFlow() {
    try {
        const res = await fetch('/api/institutional-flow');
        const d = await res.json();

        if (d.error) {
            setPill('flowPill', 'N/A', 'neutral');
            setEl('flowBadgeInner', 'No data');
            setEl('fiiNet', 'Unavailable'); setEl('diiNet', '--'); setEl('futuresFlow', '--');
            document.getElementById('flowReasons').innerHTML = '<div class="flow-reason">FII/DII data unavailable from NSE</div>';
            return;
        }

        const bias = d.cumulative_bias || 'neutral';
        setPill('flowPill', bias.replace(/_/g, ' '), biasClass(bias));
        setEl('flowBadgeInner', bias.replace(/_/g, ' ').toUpperCase());

        const fiiDii = d.fii_dii || {};
        const fiiNet = fiiDii.fii_net;
        const diiNet = fiiDii.dii_net;
        setEl('fiiNet', fiiNet !== undefined ? (fiiNet >= 0 ? '+' : '') + fmtInt(fiiNet) + ' Cr' : '--');
        setEl('diiNet', diiNet !== undefined ? (diiNet >= 0 ? '+' : '') + fmtInt(diiNet) + ' Cr' : '--');
        setEl('futuresFlow', (d.futures || {}).classification
            ? d.futures.classification.replace(/_/g, ' ').toUpperCase() : 'No futures data');

        const reasons = (d.reasons || []).filter(Boolean).slice(0, 5);
        document.getElementById('flowReasons').innerHTML = reasons.length
            ? reasons.map(r => `<div class="flow-reason">${r}</div>`).join('')
            : '<div class="flow-reason">No flow signals available</div>';
    } catch (e) {
        console.error('Flow error:', e);
        setEl('flowBadgeInner', 'Error');
    }
}

// ── VWAP ───────────────────────────────────────────────────────────────────

async function fetchVWAP() {
    try {
        const res = await fetch('/api/volume-profile');
        const d = await res.json();

        if (d.error) {
            setEl('vwapValue', 'No 5m data');
            setEl('vwapPoc', '--'); setEl('vwapVahVal', '--');
            document.getElementById('vwapSignals').innerHTML = '<div class="vwap-signal">VWAP calculated from 5m data — unavailable now</div>';
            return;
        }

        const vwap = d.vwap || {};
        const profile = d.volume_profile || {};
        const vwapVal = vwap.vwap != null && !isNaN(vwap.vwap) ? fmt(vwap.vwap, 2) : '--';
        setEl('vwapValue', vwapVal);
        setEl('vwapPoc', (profile.poc != null && !isNaN(profile.poc)) ? fmt(profile.poc, 2) : '--');
        setEl('vwapVahVal', (profile.vah && profile.val) ? `${fmt(profile.vah, 0)} / ${fmt(profile.val, 0)}` : '--');

        const pos = vwap.position || 'at';
        setPill('vwapPill', pos.toUpperCase(), pos === 'above' ? 'bullish' : pos === 'below' ? 'bearish' : 'neutral');
        setEl('vwapPill', pos.toUpperCase());

        const allSig = [...(d.vwap_signals || []), ...(d.profile_signals || []), ...(d.delta_signals || [])].filter(Boolean);
        document.getElementById('vwapSignals').innerHTML = allSig.length
            ? allSig.slice(0, 4).map(s => `<div class="vwap-signal">${s}</div>`).join('')
            : '<div class="vwap-signal">No VWAP signals (market closed)</div>';
    } catch (e) {
        console.error('VWAP error:', e);
        setEl('vwapValue', 'Error');
    }
}

// ── Deep OI ────────────────────────────────────────────────────────────────

async function fetchDeepOI() {
    try {
        const res = await fetch('/api/deep-oi');
        const d = await res.json();

        if (!d.market_open || d.error) {
            const msg = d.market_open === false
                ? 'Market closed — OI data available during market hours (9:15 AM – 3:30 PM)'
                : (d.nse_api_limited ? 'NSE option chain API deprecated — OI unavailable' : 'OI data unavailable');
            setPill('oiPill', d.market_open === false ? 'CLOSED' : 'N/A', 'neutral');
            setEl('oiBadgeInner', d.market_open === false ? 'Market Closed' : 'Unavailable');
            setEl('oiSupportWall', '--'); setEl('oiResistanceWall', '--');
            document.getElementById('oiBuildupList').innerHTML = `<div class="oi-buildup-item" style="color:var(--text-muted);font-size:0.8rem;">${msg}</div>`;
            return;
        }

        const oiBias = (d.oi_buildup || {}).oi_bias || 'neutral';
        setPill('oiPill', oiBias, biasClass(oiBias));
        setEl('oiBadgeInner', oiBias.toUpperCase());

        const walls = d.walls || {};
        setEl('oiSupportWall', walls.support ? walls.support.strike : 'None');
        setEl('oiResistanceWall', walls.resistance ? walls.resistance.strike : 'None');

        const totals = (d.oi_buildup || {}).totals || {};
        document.getElementById('oiBuildupList').innerHTML = `
            <div class="oi-buildup-item"><span>CE Long Buildup</span><span class="${totals.ce_long_buildup > 0 ? 'success' : ''}">${fmtInt(totals.ce_long_buildup)}</span></div>
            <div class="oi-buildup-item"><span>CE Short Buildup</span><span class="${totals.ce_short_buildup > 0 ? 'danger' : ''}">${fmtInt(totals.ce_short_buildup)}</span></div>
            <div class="oi-buildup-item"><span>PE Long Buildup</span><span class="${totals.pe_long_buildup > 0 ? 'success' : ''}">${fmtInt(totals.pe_long_buildup)}</span></div>
            <div class="oi-buildup-item"><span>PE Short Buildup</span><span class="${totals.pe_short_buildup > 0 ? 'danger' : ''}">${fmtInt(totals.pe_short_buildup)}</span></div>
        `;
    } catch (e) {
        console.error('Deep OI error:', e);
        setEl('oiBadgeInner', 'Error');
    }
}

// ── Trend pill ─────────────────────────────────────────────────────────────

async function fetchTrend() {
    try {
        const res = await fetch('/api/trend');
        const d = await res.json();
        setPill('trendPill', d.trend || '--', biasClass(d.trend));
    } catch (e) { }
}

// ── Live Monitor ───────────────────────────────────────────────────────────

async function fetchMonitorUpdate() {
    try {
        const res = await fetch('/api/monitor-update');
        const d = await res.json();
        const panel = document.getElementById('monitorPanel');
        if ((d.active_trade_count || 0) === 0) { panel.style.display = 'none'; return; }
        panel.style.display = 'flex';
        const first = (d.trades || [])[0];
        if (first) {
            activeTradeId = first.trade_id;
            const pnlEl = document.getElementById('monitorPnl');
            pnlEl.textContent = first.current_pnl !== null ? fmtRs(first.current_pnl) : '--';
            pnlEl.className = 'monitor-pnl ' + (first.current_pnl > 0 ? 'success' : first.current_pnl < 0 ? 'danger' : '');
            setEl('monitorAction', first.action || '--');
            setEl('monitorReason', first.reason || '');
        }
    } catch (e) { }
}

// ── News ───────────────────────────────────────────────────────────────────

async function fetchNews() {
    try {
        const res = await fetch('/api/news');
        const news = await res.json();
        const list = document.getElementById('newsList');
        if (!news || !news.length) { list.innerHTML = 'No news.'; return; }
        list.innerHTML = '<ul class="news-list">' + news.slice(0, 3).map(n =>
            `<li><span class="news-sentiment ${n.sentiment}">${n.sentiment}</span> ${n.title}</li>`
        ).join('') + '</ul>';
    } catch (e) { }
}

// ── Trade actions ──────────────────────────────────────────────────────────

async function saveTrade() {
    if (!currentSignal || !currentSignal.has_signal) { alert('No active signal to save.'); return; }
    const t = currentSignal.trade;
    const payload = {
        trade: {
            instrument_type: 'NIFTY',
            trade_type: t.option_type,
            direction: t.direction === 'bearish' ? 'SHORT' : 'LONG',
            entry: t.entry_ideal,
            stop_loss: t.stop_loss,
            target1: t.target1,
            target2: t.target2,
            quantity: t.units,
            risk_reward: t.rr_t1,
            total_risk: t.total_risk,
            strike: t.strike,
            expiry: t.expiry_display,
        },
        confidence_score: currentSignal.confidence,
        confidence_label: currentSignal.grade,
        market_trend: currentSignal.bias,
        vix: currentSignal.vix,
        days_to_expiry: currentSignal.dte,
        spot: currentSignal.spot,
        reasons: currentSignal.reasons || [],
        risk_factors: currentSignal.risk_flags || [],
        invalidation_scenarios: [`Spot crosses ${t.spot_sl}`],
    };
    try {
        const res = await fetch('/api/save-trade', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const r = await res.json();
        alert(r.message || 'Saved');
    } catch (e) { alert('Save failed'); }
}

async function activateTrade() {
    if (!currentSignal || !currentSignal.has_signal) { alert('No active signal to monitor.'); return; }
    const t = currentSignal.trade;
    const payload = {
        trade: {
            instrument_type: 'NIFTY',
            trade_type: t.option_type,
            direction: t.direction === 'bearish' ? 'SHORT' : 'LONG',
            entry: t.entry_ideal,
            stop_loss: t.stop_loss,
            target1: t.target1,
            target2: t.target2,
            quantity: t.units,
            risk_reward: t.rr_t1,
            total_risk: t.total_risk,
            strike: t.strike,
            expiry: t.expiry_display,
        },
        market_bias: currentSignal.bias,
        confidence_score: currentSignal.confidence,
    };
    try {
        const res = await fetch('/api/active-trades', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const r = await res.json();
        if (r.success) { activeTradeId = r.trade_id; alert('Trade activated for monitoring!'); fetchMonitorUpdate(); }
        else alert(r.message || 'Failed');
    } catch (e) { alert('Activation failed'); }
}

async function sendMonitorAction(action) {
    if (!activeTradeId) { alert('No active trade.'); return; }
    const labels = { EXIT: 'Manual exit', PARTIAL_BOOK: 'Booking partial profits', TRAIL_SL: 'Trailing stop loss' };
    try {
        const res = await fetch('/api/monitor-action', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ trade_id: activeTradeId, action, reason: labels[action] || 'Manual' })
        });
        const r = await res.json();
        alert(r.message);
        fetchMonitorUpdate();
    } catch (e) { }
}

// ── Wire up buttons ────────────────────────────────────────────────────────

document.getElementById('btnSaveTrade')?.addEventListener('click', saveTrade);
document.getElementById('btnActivateTrade')?.addEventListener('click', activateTrade);
document.getElementById('btnPartialBook')?.addEventListener('click', () => sendMonitorAction('PARTIAL_BOOK'));
document.getElementById('btnTrailSl')?.addEventListener('click', () => sendMonitorAction('TRAIL_SL'));
document.getElementById('btnExitTrade')?.addEventListener('click', () => sendMonitorAction('EXIT'));

// ── Refresh ────────────────────────────────────────────────────────────────

function refreshAll() {
    fetchIntradaySignal();
    fetchMarketSummary();
    fetchTrend();
    fetchChartAnalysis();
    fetchSMC();
    fetchVWAP();
    fetchDeepOI();
    fetchInstitutionalFlow();
    fetchOptionChain();
    fetchMonitorUpdate();
    fetchNews();
}

// Refresh every 30s during market hours, 5 min otherwise
setInterval(() => {
    const hour = new Date().getHours();
    const minute = new Date().getMinutes();
    const inMarket = (hour > 9 || (hour === 9 && minute >= 15)) && (hour < 15 || (hour === 15 && minute <= 30));
    if (inMarket) refreshAll();
    else fetchIntradaySignal();  // just keep morning brief fresh
}, 30000);

refreshAll();
