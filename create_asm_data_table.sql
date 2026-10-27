-- Create table asm_data in PostgreSQL
-- This table will store data from SQL Server

DROP TABLE IF EXISTS public.asm_data CASCADE;
DROP SEQUENCE IF EXISTS public.asm_data_id_seq CASCADE;

-- Create sequence for id
CREATE SEQUENCE public.asm_data_id_seq;

CREATE TABLE public.asm_data (
    id INTEGER PRIMARY KEY DEFAULT nextval('asm_data_id_seq'::regclass),
    alias VARCHAR(255),
    device_name VARCHAR(255) UNIQUE,
    ip_address VARCHAR(50),
    owner_id VARCHAR(50),
    serial_number VARCHAR(255),
    domain_name VARCHAR(255),
    logon_user VARCHAR(255),
    model VARCHAR(255),
    system_type VARCHAR(100),
    agent_version VARCHAR(50),
    last_respond TIMESTAMP,
    "encrypted" VARCHAR(50),
    group_name VARCHAR(255),
    computer_type VARCHAR(100),
    firstname VARCHAR(255),
    lastname VARCHAR(255),
    address TEXT,
    remark TEXT,
    monitor_type VARCHAR(100),
    answer TEXT,
    response_by VARCHAR(255),
    window_os VARCHAR(100),
    window_os_full VARCHAR(255),
    nessus_agent VARCHAR(50),
    asset_number VARCHAR(255),
    agent_id VARCHAR(255),
    staff_id VARCHAR(255),
    over_month INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on agent_id for faster lookups
CREATE INDEX idx_asm_data_agent_id ON public.asm_data(agent_id);

-- Create index on device_name for faster searches
CREATE INDEX idx_asm_data_device_name ON public.asm_data(device_name);

-- Add comment
COMMENT ON TABLE public.asm_data IS 'Stores ASM device data from SQL Server';

-- =====================================================
-- Alternative: Add UNIQUE constraint to existing table
-- =====================================================
-- If you have an existing table and want to add the constraint:
-- ALTER TABLE public.asm_data ADD CONSTRAINT asm_data_device_name_key UNIQUE (device_name);
-- Note: This will fail if there are duplicate device_name values
