-- GRRI-MAC Framework Database Schema
-- Azure SQL Database Serverless

-- MAC History Table
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='mac_history' AND xtype='U')
CREATE TABLE mac_history (
    id INT IDENTITY(1,1) PRIMARY KEY,
    timestamp DATETIME2 NOT NULL DEFAULT GETUTCDATE(),

    -- Composite score
    mac_score FLOAT NOT NULL,

    -- Pillar scores
    liquidity_score FLOAT,
    valuation_score FLOAT,
    positioning_score FLOAT,
    volatility_score FLOAT,
    policy_score FLOAT,

    -- Derived values
    multiplier FLOAT,
    breach_flags NVARCHAR(500),  -- JSON array

    -- Metadata
    is_live BIT DEFAULT 0,
    indicators NVARCHAR(MAX),  -- JSON object with raw indicator values

    -- Index for time-based queries
    INDEX idx_timestamp (timestamp)
);
GO

-- View for daily averages
CREATE OR ALTER VIEW mac_daily_average AS
SELECT
    CAST(timestamp AS DATE) as date,
    AVG(mac_score) as avg_mac,
    AVG(liquidity_score) as avg_liquidity,
    AVG(valuation_score) as avg_valuation,
    AVG(positioning_score) as avg_positioning,
    AVG(volatility_score) as avg_volatility,
    AVG(policy_score) as avg_policy,
    COUNT(*) as sample_count
FROM mac_history
GROUP BY CAST(timestamp AS DATE);
GO

-- Stored procedure to get history
CREATE OR ALTER PROCEDURE sp_get_mac_history
    @days INT = 30
AS
BEGIN
    SELECT
        timestamp,
        mac_score,
        liquidity_score,
        valuation_score,
        positioning_score,
        volatility_score,
        policy_score,
        is_live
    FROM mac_history
    WHERE timestamp >= DATEADD(day, -@days, GETUTCDATE())
    ORDER BY timestamp ASC;
END;
GO

-- Stored procedure to cleanup old data (keep 1 year)
CREATE OR ALTER PROCEDURE sp_cleanup_old_data
AS
BEGIN
    DELETE FROM mac_history
    WHERE timestamp < DATEADD(year, -1, GETUTCDATE());

    SELECT @@ROWCOUNT as deleted_count;
END;
GO
