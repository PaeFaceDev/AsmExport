-- Add UNIQUE constraint on device_name to existing asm_data table
-- Run this in PostgreSQL if you already have data in the table

ALTER TABLE public.asm_data ADD CONSTRAINT asm_data_device_name_key UNIQUE (device_name);

-- If the above fails due to duplicate device_name values, run this to find duplicates:
-- SELECT device_name, COUNT(*) 
-- FROM public.asm_data 
-- GROUP BY device_name 
-- HAVING COUNT(*) > 1;
