"""
Volume Profile & VWAP Analysis Service
Institutional-grade volume analysis for NIFTY 50.

Calculates:
- VWAP (Volume Weighted Average Price) with standard deviation bands
- Anchored VWAP (from session open or key level)
- Volume Profile: POC, Value Area High/Low, Volume Nodes
- Volume Delta: Buying vs Selling pressure approximation
"""

import math
import pandas as pd
import numpy as np


def calculate_vwap(data, anchor_index=0):
    """
    Calculate VWAP from anchor_index to the end of the data.
    Standard VWAP uses typical price (H+L+C)/3.
    
    Returns dict with vwap series and current value.
    """
    if data is None or len(data) < 3:
        return None
    
    subset = data.iloc[anchor_index:].copy()
    typical_price = (subset['High'] + subset['Low'] + subset['Close']) / 3
    
    cumulative_tp_vol = (typical_price * subset['Volume']).cumsum()
    cumulative_vol = subset['Volume'].cumsum()
    
    vwap = cumulative_tp_vol / cumulative_vol
    
    # Standard deviation bands
    squared_diff = ((typical_price - vwap) ** 2) * subset['Volume']
    cumulative_sq_diff = squared_diff.cumsum()
    variance = cumulative_sq_diff / cumulative_vol
    std_dev = np.sqrt(variance)
    
    current_vwap = float(vwap.iloc[-1])
    current_std = float(std_dev.iloc[-1])
    current_price = float(subset['Close'].iloc[-1])
    
    # Position relative to VWAP
    deviation = (current_price - current_vwap) / max(current_std, 0.001)
    
    return {
        "vwap": round(current_vwap, 2),
        "std_dev": round(current_std, 2),
        "deviation": round(deviation, 2),
        "band_1_upper": round(current_vwap + current_std, 2),
        "band_1_lower": round(current_vwap - current_std, 2),
        "band_2_upper": round(current_vwap + 2 * current_std, 2),
        "band_2_lower": round(current_vwap - 2 * current_std, 2),
        "band_3_upper": round(current_vwap + 3 * current_std, 2),
        "band_3_lower": round(current_vwap - 3 * current_std, 2),
        "position": "above" if current_price > current_vwap else "below" if current_price < current_vwap else "at",
        "distance_from_vwap": round(current_price - current_vwap, 2),
        "distance_pct": round((current_price - current_vwap) / max(current_vwap, 1) * 100, 3),
    }


def calculate_anchored_vwap(data, anchor_price, anchor_index=0):
    """
    Calculate VWAP anchored from a specific price level and index.
    Used for finding fair value from a key session open or swing point.
    """
    if data is None or len(data) < 3:
        return None
    
    subset = data.iloc[anchor_index:].copy()
    typical_price = (subset['High'] + subset['Low'] + subset['Close']) / 3
    
    cumulative_tp_vol = (typical_price * subset['Volume']).cumsum()
    cumulative_vol = subset['Volume'].cumsum()
    
    vwap = cumulative_tp_vol / cumulative_vol
    current_vwap = float(vwap.iloc[-1])
    current_price = float(subset['Close'].iloc[-1])
    
    return {
        "anchor_price": round(anchor_price, 2),
        "vwap": round(current_vwap, 2),
        "deviation": round(current_price - current_vwap, 2),
        "position": "above" if current_price > current_vwap else "below" if current_price < current_vwap else "at",
    }


def calculate_volume_profile(data, num_bins=30):
    """
    Calculate Volume Profile from intraday data.
    
    Returns:
    - POC: Price level with highest volume
    - VAH/VAL: Value Area High/Low (70% of total volume around POC)
    - Volume nodes: Clusters of high volume
    """
    if data is None or len(data) < 10:
        return None
    
    # Use typical price for each candle
    typical_prices = ((data['High'] + data['Low'] + data['Close']) / 3).values
    volumes = data['Volume'].values
    
    price_min = float(data['Low'].min())
    price_max = float(data['High'].max())
    
    if price_max <= price_min:
        return None
    
    bin_edges = np.linspace(price_min, price_max, num_bins + 1)
    bin_volumes = np.zeros(num_bins)
    bin_prices = []
    
    for i in range(num_bins):
        bin_low = bin_edges[i]
        bin_high = bin_edges[i + 1]
        bin_prices.append((bin_low + bin_high) / 2)
        
        # Sum volume for candles whose typical price falls in this bin
        mask = (typical_prices >= bin_low) & (typical_prices < bin_high)
        bin_volumes[i] = volumes[mask].sum()
    
    # POC: Bin with highest volume
    poc_idx = int(np.argmax(bin_volumes))
    poc_price = float(round(bin_prices[poc_idx], 2))
    poc_volume = float(bin_volumes[poc_idx])
    
    total_volume = bin_volumes.sum()
    
    # Value Area: 70% of total volume around POC
    sorted_by_distance = sorted(enumerate(bin_volumes), key=lambda x: abs(x[0] - poc_idx))
    
    cumulative_vol = 0
    value_area_indices = []
    for idx, vol in sorted_by_distance:
        cumulative_vol += vol
        value_area_indices.append(idx)
        if cumulative_vol >= total_volume * 0.70:
            break
    
    vah_idx = max(value_area_indices)
    val_idx = min(value_area_indices)
    vah_price = float(round(bin_prices[vah_idx], 2))
    val_price = float(round(bin_prices[val_idx], 2))
    
    # Volume nodes: bins with volume > 1.5x average
    avg_volume = total_volume / num_bins
    nodes = []
    for i, vol in enumerate(bin_volumes):
        if vol > avg_volume * 1.5:
            nodes.append({
                "price": round(bin_prices[i], 2),
                "volume": float(vol),
                "node_strength": float(round(vol / avg_volume, 2))
            })
    
    # Sort nodes by strength
    nodes = sorted(nodes, key=lambda x: x["node_strength"], reverse=True)[:5]
    
    current_price = float(data['Close'].iloc[-1])
    
    return {
        "poc": poc_price,
        "poc_volume": round(poc_volume, 0),
        "vah": vah_price,
        "val": val_price,
        "value_area_width": float(round(vah_price - val_price, 2)),
        "total_volume": float(round(total_volume, 0)),
        "volume_nodes": nodes,
        "current_position": "above_poc" if current_price > poc_price else "below_poc" if current_price < poc_price else "at_poc",
        "in_value_area": bool(val_price <= current_price <= vah_price),
    }


def calculate_volume_delta(data):
    """
    Approximate buying vs selling pressure using candle close position.
    
    Close near high = buying pressure
    Close near low = selling pressure
    """
    if data is None or len(data) < 5:
        return None
    
    highs = data['High'].values
    lows = data['Low'].values
    closes = data['Close'].values
    opens = data['Open'].values
    volumes = data['Volume'].values
    
    buy_vol = 0
    sell_vol = 0
    neutral_vol = 0
    
    delta_series = []
    
    for i in range(len(data)):
        candle_range = highs[i] - lows[i]
        if candle_range == 0:
            delta = 0
        else:
            # Delta based on close position within the candle
            close_position = (closes[i] - lows[i]) / candle_range
            
            # Adjust for candle direction
            if closes[i] > opens[i]:  # Bullish candle
                delta = volumes[i] * close_position
            elif closes[i] < opens[i]:  # Bearish candle
                delta = -volumes[i] * (1 - close_position)
            else:
                delta = 0
        
        delta_series.append(delta)
        
        if delta > 0:
            buy_vol += delta
        elif delta < 0:
            sell_vol += abs(delta)
        else:
            neutral_vol += volumes[i]
    
    total_delta = sum(delta_series)
    cumulative_delta = np.cumsum(delta_series)
    
    # Delta trend over last 10 candles
    recent_delta = sum(delta_series[-10:]) if len(delta_series) >= 10 else sum(delta_series)
    
    return {
        "total_delta": float(round(total_delta, 0)),
        "buy_volume": float(round(buy_vol, 0)),
        "sell_volume": float(round(sell_vol, 0)),
        "neutral_volume": float(round(neutral_vol, 0)),
        "delta_bias": "buying" if total_delta > 0 else "selling" if total_delta < 0 else "neutral",
        "recent_delta": float(round(recent_delta, 0)),
        "recent_bias": "buying" if recent_delta > 0 else "selling" if recent_delta < 0 else "neutral",
        "cumulative_delta_end": round(float(cumulative_delta[-1]), 0) if len(cumulative_delta) > 0 else 0,
    }


def analyze_vwap_and_profile(data_5m, data_daily=None):
    """
    Main analysis function combining VWAP, Volume Profile, and Volume Delta.
    
    data_5m: 5-minute intraday data for VWAP and Volume Profile
    data_daily: Optional daily data for broader context
    """
    if data_5m is None or len(data_5m) < 10:
        return {"error": "Insufficient 5-minute data for VWAP/Volume Profile analysis"}
    
    # Standard VWAP (from start of data)
    vwap = calculate_vwap(data_5m)
    
    # Anchored VWAP from session open (first candle)
    session_open = float(data_5m['Open'].iloc[0])
    anchored_vwap = calculate_anchored_vwap(data_5m, session_open, anchor_index=0)
    
    # Volume Profile
    vol_profile = calculate_volume_profile(data_5m)
    
    # Volume Delta
    vol_delta = calculate_volume_delta(data_5m)
    
    current_price = float(data_5m['Close'].iloc[-1])
    
    # VWAP-based signals
    vwap_signals = []
    if vwap:
        if abs(vwap["deviation"]) < 0.5:
            vwap_signals.append("Price near VWAP — balanced, wait for directional move")
        elif vwap["deviation"] > 2:
            vwap_signals.append("Price extended above VWAP (+2σ) — mean reversion risk, consider shorts near resistance")
        elif vwap["deviation"] < -2:
            vwap_signals.append("Price extended below VWAP (-2σ) — mean reversion risk, consider longs near support")
        elif vwap["deviation"] > 0.5:
            vwap_signals.append("Price above VWAP — bullish intraday bias")
        elif vwap["deviation"] < -0.5:
            vwap_signals.append("Price below VWAP — bearish intraday bias")
    
    # Volume Profile signals
    profile_signals = []
    if vol_profile:
        if vol_profile["in_value_area"]:
            profile_signals.append(f"Price inside Value Area ({vol_profile['val']}-{vol_profile['vah']}) — normal activity zone")
        elif current_price > vol_profile["vah"]:
            profile_signals.append(f"Price above Value Area High ({vol_profile['vah']}) — potential overextension")
        elif current_price < vol_profile["val"]:
            profile_signals.append(f"Price below Value Area Low ({vol_profile['val']}) — potential oversold")
    
    # Delta signals
    delta_signals = []
    if vol_delta:
        if vol_delta["recent_bias"] == "buying" and vol_delta["delta_bias"] == "buying":
            delta_signals.append("Consistent buying pressure across session — bulls in control")
        elif vol_delta["recent_bias"] == "selling" and vol_delta["delta_bias"] == "selling":
            delta_signals.append("Consistent selling pressure across session — bears in control")
        elif vol_delta["recent_bias"] != vol_delta["delta_bias"]:
            delta_signals.append(f"Shift in delta: session was {vol_delta['delta_bias']}, recently {vol_delta['recent_bias']} — potential reversal")
    
    return {
        "vwap": vwap,
        "anchored_vwap": anchored_vwap,
        "volume_profile": vol_profile,
        "volume_delta": vol_delta,
        "vwap_signals": vwap_signals,
        "profile_signals": profile_signals,
        "delta_signals": delta_signals,
        "current_price": round(current_price, 2),
    }
