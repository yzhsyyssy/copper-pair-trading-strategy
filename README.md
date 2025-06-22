# Copper Pair Trading Strategy

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

This repository contains a statistical arbitrage strategy for trading copper futures pairs between International Copper (INE.BC) and Shanghai Copper (SHFE.CU). The strategy leverages the price correlation between these two related copper futures contracts to capture price divergence and convergence opportunities.

## Strategy Logic

The core of this strategy is based on calculating and comparing the linear regression slopes of price movements for both copper contracts:

1. **Signal Generation**: 
   - Calculate linear regression slopes for both INE.BC and SHFE.CU price series
   - Determine trading direction based on the slope differential
   - When INE.BC slope > SHFE.CU slope: Long INE.BC, Short SHFE.CU
   - When INE.BC slope < SHFE.CU slope: Short INE.BC, Long SHFE.CU

2. **Position Management**:
   - Automatically track and switch to main contracts
   - Close positions when slope differential changes direction
   - Implement daily stop-loss at 1% drawdown
   - Take profit when cumulative 3-day returns exceed 0.5%

## Key Features

- **Dynamic Parameter Adjustment**: Automatically adjusts lookback periods based on different time ranges
- **Risk Management**: Implements strict stop-loss and take-profit mechanisms
- **Main Contract Handling**: Automatically switches to the main contract to avoid delivery risks
- **Daily PnL Tracking**: Calculates and records daily performance metrics

## Requirements

- Python 3.6+
- NumPy
- Pandas
- GoldMiner API (for execution and data access)

## Configuration

The strategy includes several configurable parameters:

- **Lookback Period**: Adjustable between 24-30 bars depending on market conditions
- **Position Size**: Default is 500,000 units per side
- **Stop Loss**: 1% daily loss threshold
- **Take Profit**: 0.5% cumulative 3-day profit threshold

## Backtest Results

The strategy is configured for backtesting from November 19, 2020, to April 30, 2025, with the following parameters:

- Initial Capital: 2,000,000
- Commission Rate: 0.01%
- Slippage Rate: 0.01%

## Usage

```python
# Run backtest
if __name__ == '__main__':
    run(strategy_id='your_strategy_id',
        filename='main.py',
        mode=MODE_BACKTEST,
        token='your_token',
        backtest_start_time='2020-11-19 00:00:00',
        backtest_end_time='2025-04-30 00:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=2000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)
```

## Disclaimer

This strategy is provided for educational and research purposes only. Trading futures involves substantial risk of loss and is not suitable for all investors. Past performance is not indicative of future results.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
