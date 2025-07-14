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