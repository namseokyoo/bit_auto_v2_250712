# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Bitcoin automated trading system (version 2) that utilizes Oracle Cloud as the server infrastructure. The system integrates multiple data sources and AI analysis to make automated trading decisions on the Upbit cryptocurrency exchange.

### Core Components

1. **Trading Engine**: Automated Bitcoin trading using Upbit API
2. **Strategy Module**: Trading strategies based on technical analysis, news sentiment, and AI recommendations
3. **Web Interface**: Control panel for enabling/disabling automated trading
4. **Data Recording**: Comprehensive logging of all trading activities
5. **AI Analysis System**: Weekly performance analysis and strategy optimization
6. **Growth System**: Self-improving algorithms based on historical performance

## Architecture Rules

### API Integration
- Use Upbit API for all trading operations
- Implement proper rate limiting and error handling for API calls
- Store API keys and secrets securely (never commit to repository)
- Use environment variables for all sensitive configuration

### Trading Safety
- Implement multiple safety checks before executing trades
- Always validate market conditions before placing orders
- Include emergency stop mechanisms
- Log all trading decisions with detailed reasoning

### Data Management
- Record all trading activities with timestamps
- Store market data, trading signals, and AI recommendations
- Implement data backup and recovery procedures
- Structure data for weekly AI analysis and reporting

### Web Interface Security
- Implement proper authentication for trading controls
- Use HTTPS for all web communications
- Validate all user inputs
- Implement session management and timeout controls

### AI/ML Components
- Separate model training from live trading
- Implement model versioning and rollback capabilities
- Store model performance metrics
- Use backtesting before deploying new strategies

## Development Guidelines

### Code Structure
- Separate trading logic, data processing, and web interface into distinct modules
- Use configuration files for strategy parameters
- Implement proper logging throughout the application
- Create comprehensive error handling and recovery mechanisms

### Testing Requirements
- Unit tests for all trading logic
- Integration tests for API interactions
- Backtesting framework for strategy validation
- End-to-end tests for critical trading paths

### Deployment
- Use Oracle Cloud infrastructure
- Implement blue-green deployment for zero-downtime updates
- Configure monitoring and alerting systems
- Set up automated backups for trading data

### Security Considerations
- Never store API keys in code or configuration files committed to git
- Implement proper access controls for trading operations
- Use secure communication channels for all external API calls
- Regular security audits of trading logic and data handling

## Technology Stack Guidelines

### Recommended Technologies
- **Backend**: Python/Node.js for trading engine and API integrations
- **Database**: PostgreSQL/MongoDB for trade data storage
- **Web Framework**: React/Vue.js for control interface
- **Cloud**: Oracle Cloud Infrastructure
- **Monitoring**: Implement logging and monitoring systems
- **Scheduling**: Cron jobs or task schedulers for periodic operations

### Development Commands
- Set up automated testing: `npm test` or `pytest`
- Code linting: Configure ESLint/flake8
- Build commands: Set up build pipelines for deployment
- Database migrations: Implement schema version control

## Critical Development Rules

1. **Never commit sensitive data**: API keys, secrets, or personal trading information
2. **Always test trading logic thoroughly** before deploying to live environment
3. **Implement comprehensive logging** for all trading decisions and system events
4. **Use paper trading mode** for testing new strategies
5. **Maintain detailed documentation** of all trading algorithms and decision processes

## Professional Trading Strategy Implementation

### Strategy Documentation
- **Primary Reference**: `docs/TRADING_STRATEGY_LOGIC.md` - Comprehensive professional trading strategy documentation
- **Implementation Module**: `core/professional_strategies.py` - Professional-grade strategy implementations

### Strategy Categories

#### Hourly Strategies (H1-H8)
1. **H1: EMA Crossover** - Adaptive period EMA with multiple filters and dynamic stop loss
2. **H2: RSI Divergence** - Regular and hidden divergence detection with multi-timeframe confirmation
3. **H3: Pivot Point Bounce** - Standard and Camarilla pivots with candlestick pattern recognition
4. **H4: VWAP Pullback** - VWAP bands with cumulative delta and anchored VWAP
5. **H5: MACD Histogram** - Momentum change detection with divergence analysis
6. **H6: Bollinger Band Squeeze** - Volatility compression and expansion strategies
7. **H7: Open Interest & Funding** - Market sentiment and position bias analysis
8. **H8: Flag/Pennant Patterns** - Continuation pattern recognition with volume confirmation

#### Daily Strategies (D1-D8)
1. **D1: Weekly Filter + MA50** - Multi-timeframe trend following
2. **D2: Ichimoku Cloud** - Cloud breakout and bounce strategies
3. **D3: Bollinger Band Width** - Historical volatility compression
4. **D4: Fear & Greed Index** - Contrarian sentiment trading
5. **D5: Golden Cross Pullback** - First pullback after major trend change
6. **D6: MVRV Z-Score** - On-chain value analysis
7. **D7: Stochastic RSI** - Oversold/overbought reversals
8. **D8: ADX Trend Strength** - Market regime adaptive meta-strategy

### Risk Management Framework

#### Position Sizing
- **Kelly Criterion** (Conservative): 25% of optimal Kelly fraction
- **ATR-based Stop Loss**: Dynamic stops based on market volatility
- **Volume Profile POC**: Entry/exit optimization using Point of Control
- **Correlation Management**: Maximum 2 correlated positions (>0.7 correlation)

#### Loss Limits
- **Daily**: 5% maximum loss
- **Weekly**: 10% maximum loss
- **Monthly**: 15% maximum loss
- **Equity Curve Filter**: Stop trading below 20-day MA of equity

#### Partial Profit Taking
- **1.5R**: Exit 30% of position
- **2.5R**: Exit additional 30%
- **4.0R**: Exit remaining 40%

### Backtesting Requirements

#### Performance Targets
- **Sharpe Ratio**: > 1.5
- **Sortino Ratio**: > 2.0
- **Maximum Drawdown**: < 20%
- **Win Rate**: > 45%
- **Risk-Reward Ratio**: > 1.5
- **Annual Return**: 30-50%

#### Validation Process
1. **Walk-Forward Analysis**: 6 months training, 2 months validation
2. **Monte Carlo Simulation**: 1000 iterations minimum
3. **Stress Testing**: March 2020, May 2022 extreme market conditions
4. **Slippage & Commission**: 0.1% slippage, 0.05% commission

### Implementation Guidelines

#### Strategy Selection
- Strategies are selected based on market regime (trending/ranging)
- ADX > 30: Use trend-following strategies (H1, D1, D2)
- ADX < 20: Use mean-reversion strategies (H3, H6, D3)
- 20 < ADX < 30: Use momentum strategies (H4, H5, D7)

#### Entry Filters
1. **Volume Confirmation**: > 1.5x average volume
2. **Volatility Range**: ATR between 1.5% and 8% of price
3. **Trend Alignment**: Price position relative to major MAs
4. **Market Structure**: Support/resistance levels
5. **Sentiment Check**: Funding rate and open interest

#### Exit Rules
1. **Stop Loss**: ATR-based or structure-based (tighter)
2. **Time Stop**: Maximum 72 hours for hourly, 10 days for daily
3. **Volatility Exit**: 2.5x ATR from entry
4. **Partial Profits**: Scaled exits at R-multiples
5. **Reversal Signals**: Opposite strategy signal

### Continuous Improvement Process

#### Weekly Review
- Performance analysis per strategy
- Comparison of expected vs actual results
- Market regime change detection
- Parameter fine-tuning

#### Monthly Optimization
- Backtesting re-run with recent data
- Filter addition/removal based on performance
- Position sizing adjustments
- Correlation matrix updates

#### Quarterly Strategy Review
- Strategy effectiveness evaluation
- New strategy addition consideration
- Underperforming strategy removal/modification
- Risk limit recalibration

### Safety Mechanisms

#### Circuit Breakers
- **Rapid Drawdown**: Pause trading if -3% in 1 hour
- **Correlation Spike**: Reduce positions if correlation > 0.9
- **Volatility Explosion**: Reduce leverage if ATR > 10%
- **Technical Failure**: Automatic position closure on system errors

#### Monitoring Requirements
- Real-time P&L tracking
- Strategy performance dashboard
- Risk metric alerts
- Order execution monitoring
- API health checks

### Advanced Features

#### Machine Learning Integration
- **Feature Engineering**: Technical indicators, market microstructure, sentiment
- **Model Types**: Random Forest for signal filtering, LSTM for price prediction
- **Validation**: Out-of-sample testing mandatory
- **Deployment**: A/B testing framework for new models

#### Market Microstructure Analysis
- **Order Book Imbalance**: Bid/ask ratio monitoring
- **Large Trade Detection**: Whale activity tracking
- **Liquidation Heatmaps**: Avoid crowded stop levels
- **Funding Rate Arbitrage**: Exploit funding inefficiencies

### Testing Commands
```bash
# Run strategy backtests
python backtest.py --strategy all --period 6m

# Analyze strategy performance
python analyze_performance.py --detailed

# Run paper trading simulation
python paper_trade.py --strategies h1,h2,h3,h4

# Generate strategy report
python generate_report.py --format pdf
```