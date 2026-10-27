import configparser
import pyodbc
import psycopg2
import pandas as pd
from datetime import datetime
import os
import requests
import json
import logging
from logging.handlers import RotatingFileHandler

def setup_logging():
    """Setup comprehensive logging system"""
    # Create logs directory if it doesn't exist
    logs_dir = 'logs'
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Generate log filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(logs_dir, f'asm_export_{timestamp}.log')
    
    # Create logger
    logger = logging.getLogger('asm_export')
    logger.setLevel(logging.DEBUG)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # File handler - detailed logs
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler - important messages only
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Log file handler for SQL queries only
    sql_log_file = os.path.join(logs_dir, f'sql_queries_{timestamp}.log')
    sql_handler = RotatingFileHandler(
        sql_log_file,
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    sql_handler.setLevel(logging.DEBUG)
    sql_formatter = logging.Formatter('%(asctime)s - %(message)s')
    sql_handler.setFormatter(sql_formatter)
    
    # Create separate logger for SQL
    sql_logger = logging.getLogger('sql_logger')
    sql_logger.setLevel(logging.DEBUG)
    sql_logger.handlers.clear()
    sql_logger.addHandler(sql_handler)
    
    logger.info(f"Logging initialized. Log file: {log_file}")
    logger.info(f"SQL log file: {sql_log_file}")
    
    return logger, sql_logger

def read_config(config_file='conf.ini', logger=None):
    """Read configuration from conf.ini file"""
    if logger:
        logger.info(f"Reading configuration from {config_file}")
    
    config = configparser.ConfigParser()
    config.read(config_file)
    
    # Validate required sections
    required_sections = ['SQLSERVER', 'POSTGRESQL', 'EXPORT']
    for section in required_sections:
        if section not in config:
            error_msg = f"Missing required section [{section}] in configuration file"
            if logger:
                logger.error(error_msg)
            raise ValueError(error_msg)
    
    # Validate SQLSERVER settings
    sql_required = ['server', 'database', 'username', 'password', 'driver']
    for key in sql_required:
        if key not in config['SQLSERVER']:
            error_msg = f"Missing required key '{key}' in [SQLSERVER] section"
            if logger:
                logger.error(error_msg)
            raise ValueError(error_msg)
    
    # Validate POSTGRESQL settings
    pg_required = ['host', 'port', 'username', 'password']
    for key in pg_required:
        if key not in config['POSTGRESQL']:
            error_msg = f"Missing required key '{key}' in [POSTGRESQL] section"
            if logger:
                logger.error(error_msg)
            raise ValueError(error_msg)
    
    # Optional database name with default
    if 'database' not in config['POSTGRESQL']:
        config['POSTGRESQL']['database'] = 'linebot'
        if logger:
            logger.info("Using default PostgreSQL database: linebot")
    
    # Optional table name with default
    if 'table' not in config['POSTGRESQL']:
        config['POSTGRESQL']['table'] = 'asm_data'
        if logger:
            logger.info("Using default PostgreSQL table: asm_data")
    
    # Validate EXPORT settings with defaults
    if 'txt_file' not in config['EXPORT']:
        config['EXPORT']['txt_file'] = 'output.txt'
    if 'excel_file' not in config['EXPORT']:
        config['EXPORT']['excel_file'] = 'output.xlsx'
    if 'sheet_name' not in config['EXPORT']:
        config['EXPORT']['sheet_name'] = 'Sheet1'
    
    # Validate WEBHOOK settings with defaults
    if 'WEBHOOK' not in config:
        config['WEBHOOK'] = {}
    if 'enabled' not in config['WEBHOOK']:
        config['WEBHOOK']['enabled'] = 'false'
    if 'url' not in config['WEBHOOK']:
        config['WEBHOOK']['url'] = ''
    
    if logger:
        logger.info("Configuration loaded successfully")
        logger.debug(f"SQL Server: {config['SQLSERVER']['server']}/{config['SQLSERVER']['database']}")
        logger.debug(f"PostgreSQL: {config['POSTGRESQL']['host']}/{config['POSTGRESQL']['database']}")
        logger.debug(f"Webhook enabled: {config['WEBHOOK']['enabled']}")
    
    return config

def connect_sql_server(config, logger=None):
    """Connect to SQL Server"""
    sql_config = config['SQLSERVER']
    connection_string = (
        f"DRIVER={{{sql_config['driver']}}};"
        f"SERVER={sql_config['server']};"
        f"DATABASE={sql_config['database']};"
        f"UID={sql_config['username']};"
        f"PWD={sql_config['password']};"
        f"TrustServerCertificate=yes"
    )
    if logger:
        logger.debug(f"SQL Server connection string (password hidden): SERVER={sql_config['server']}; DATABASE={sql_config['database']}")
    return pyodbc.connect(connection_string)

def connect_postgresql(config, logger=None):
    """Connect to PostgreSQL"""
    pg_config = config['POSTGRESQL']
    if logger:
        logger.debug(f"PostgreSQL connection: host={pg_config['host']}, port={pg_config['port']}, database={pg_config['database']}")
    return psycopg2.connect(
        host=pg_config['host'],
        port=pg_config['port'],
        database=pg_config['database'],
        user=pg_config['username'],
        password=pg_config['password']
    )

def execute_sql_query(sql_conn, query, logger=None):
    """Execute SQL query and return data as DataFrame"""
    if logger:
        logger.debug("Executing SQL query...")
    cursor = sql_conn.cursor()
    cursor.execute(query)
    columns = [column[0] for column in cursor.description]
    data = cursor.fetchall()
    df = pd.DataFrame.from_records(data, columns=columns)
    if logger:
        logger.info(f"Query executed successfully. Retrieved {len(df)} rows")
    return df

def create_postgresql_table(pg_conn, df, table_name, logger=None):
    """Create or recreate table in PostgreSQL with proper schema"""
    cursor = pg_conn.cursor()
    
    # Drop existing table if it exists
    if logger:
        logger.info(f"Dropping existing table {table_name} if exists...")
    cursor.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
    cursor.execute(f"DROP SEQUENCE IF EXISTS {table_name}_id_seq CASCADE")
    pg_conn.commit()
    
    # Create sequence
    if logger:
        logger.info(f"Creating sequence {table_name}_id_seq...")
    cursor.execute(f"CREATE SEQUENCE {table_name}_id_seq")
    pg_conn.commit()
    
    # Create table with proper schema
    if logger:
        logger.info(f"Creating table {table_name}...")
    create_table_sql = f"""
    CREATE TABLE {table_name} (
        id INTEGER PRIMARY KEY DEFAULT nextval('{table_name}_id_seq'::regclass),
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
    )
    """
    cursor.execute(create_table_sql)
    pg_conn.commit()
    
    # Create indexes
    if logger:
        logger.info(f"Creating indexes...")
    cursor.execute(f"CREATE INDEX idx_{table_name}_agent_id ON {table_name}(agent_id)")
    cursor.execute(f"CREATE INDEX idx_{table_name}_device_name ON {table_name}(device_name)")
    pg_conn.commit()
    
    if logger:
        logger.info(f"Table {table_name} created successfully with UNIQUE constraint on device_name")

def upsert_postgresql_data(pg_conn, df, table_name, logger=None):
    """Insert or update data in PostgreSQL table using device_name as key"""
    cursor = pg_conn.cursor()
    
    # Convert column names to match PostgreSQL table (device_name, ip_address, etc.)
    original_columns = df.columns.tolist()
    if logger:
        logger.debug(f"Original columns from SQL Server: {original_columns}")
    
    # Mapping SQL Server columns to PostgreSQL columns
    column_mapping = {
        'Alias': 'alias',
        'DeviceName': 'device_name',
        'IPAddress': 'ip_address',
        'OwnerID': 'owner_id',
        'SerialNumber': 'serial_number',
        'DomainName': 'domain_name',
        'LogonUser': 'logon_user',
        'Model': 'model',
        'SystemType': 'system_type',
        'AgentVersion': 'agent_version',
        'LastRespond': 'last_respond',
        'encrypted': 'encrypted',
        'GroupName': 'group_name',
        'ComputerType': 'computer_type',
        'FIRSTNAME': 'firstname',
        'LASTNAME': 'lastname',
        'ADDRESS': 'address',
        'Remark': 'remark',
        'MonitorType': 'monitor_type',
        'Answer': 'answer',
        'ResponseBy': 'response_by',
        'WindowOS': 'window_os',
        'WindowOSFull': 'window_os_full',
        'NessusAgent': 'nessus_agent',
        'AssetNumber': 'asset_number',
        'AgentID': 'agent_id',
        'StaffID': 'staff_id',
        'OverMonth': 'over_month'
    }
    
    # Rename columns in DataFrame
    df = df.rename(columns=column_mapping)
    if logger:
        logger.debug(f"Converted columns: {df.columns.tolist()}")
    
    # Prepare column names for SQL (exclude id column)
    columns = [col for col in df.columns.tolist() if col != 'id']
    columns_str = ', '.join(columns)
    placeholders = ', '.join(['%s'] * len(columns))
    
    # Prepare update clause (exclude id and device_name from update)
    update_columns = [col for col in columns if col != 'device_name']
    update_clause = ', '.join([f"{col} = EXCLUDED.{col}" for col in update_columns])
    update_clause += ", updated_at = CURRENT_TIMESTAMP"
    
    # Prepare UPSERT statement with nextval for id
    upsert_sql = f"""
    INSERT INTO {table_name} (id, {columns_str})
    VALUES (nextval('asm_data_id_seq'::regclass), {placeholders})
    ON CONFLICT (device_name)
    DO UPDATE SET {update_clause}
    """
    
    if logger:
        logger.debug(f"UPSERT SQL prepared with {len(columns)} columns")
    
    # Check which device_names already exist
    device_names = df['device_name'].tolist()
    if logger:
        logger.info(f"Total device_names to process: {len(device_names)}")
        logger.debug(f"Sample device_names: {device_names[:5]}")
    
    if device_names:
        # Filter out None values
        valid_device_names = [dn for dn in device_names if dn is not None and dn != '']
        if logger:
            logger.debug(f"Valid device_names (not None/empty): {len(valid_device_names)}")
        
        if valid_device_names:
            check_sql = f"SELECT device_name FROM {table_name} WHERE device_name = ANY(%s)"
            cursor.execute(check_sql, (valid_device_names,))
            existing_devices = set(row[0] for row in cursor.fetchall())
            if logger:
                logger.info(f"Existing devices in database: {len(existing_devices)}")
        else:
            existing_devices = set()
            if logger:
                logger.warning("No valid device_names found")
    else:
        existing_devices = set()
        if logger:
            logger.warning("No device_names found in data")
    
    # Insert/Update data in batches
    batch_size = 1000
    insert_count = 0
    update_count = 0
    error_count = 0
    show_error_details = True  # Show first few errors in detail
    
    for i in range(0, len(df), batch_size):
        batch = df.iloc[i:i+batch_size]
        for idx, row in batch.iterrows():
            # Exclude id from row data
            row_data = [row[col] for col in columns]
            device_name = row['device_name']
            try:
                cursor.execute(upsert_sql, tuple(row_data))
                if device_name in existing_devices:
                    update_count += 1
                else:
                    insert_count += 1
                    existing_devices.add(device_name)
            except Exception as e:
                error_count += 1
                if show_error_details and error_count <= 3:
                    if logger:
                        logger.error(f"Error processing row {idx} for device {device_name}: {str(e)}")
                        logger.error(f"Columns: {columns}")
                        logger.error(f"Row data length: {len(row_data)}")
                elif error_count == 4:
                    if logger:
                        logger.info("Suppressing further error details (too many errors)...")
                pg_conn.rollback()
        
        pg_conn.commit()
        if logger:
            logger.info(f"Processed {min(i+batch_size, len(df))} / {len(df)} rows")
    
    if error_count > 0:
        if logger:
            logger.warning(f"{error_count} rows had errors during processing")
    
    if logger:
        logger.info(f"Successfully processed {len(df)} rows in PostgreSQL")
        logger.info(f"  - Inserted: {insert_count}")
        logger.info(f"  - Updated: {update_count}")

def ensure_directory_exists(filename, logger=None):
    """Create directory if it doesn't exist"""
    directory = os.path.dirname(filename)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
        if logger:
            logger.info(f"Created directory: {directory}")

def export_to_text(df, filename, logger=None):
    """Export DataFrame to text file with timestamp"""
    # Generate timestamp in yyyyMMddHHmmss format
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    
    # Insert timestamp before file extension
    base, ext = os.path.splitext(filename)
    timestamped_filename = f"{base}_{timestamp}{ext}"
    
    ensure_directory_exists(timestamped_filename, logger)
    df.to_csv(timestamped_filename, sep='\t', index=False, encoding='utf-8')
    if logger:
        logger.info(f"Data exported to {timestamped_filename}")
    return timestamped_filename

def export_to_excel(df, filename, sheet_name, logger=None):
    """Export DataFrame to Excel file with timestamp"""
    # Generate timestamp in yyyyMMddHHmmss format
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    
    # Insert timestamp before file extension
    base, ext = os.path.splitext(filename)
    timestamped_filename = f"{base}_{timestamp}{ext}"
    
    ensure_directory_exists(timestamped_filename, logger)
    df.to_excel(timestamped_filename, sheet_name=sheet_name, index=False, engine='openpyxl')
    if logger:
        logger.info(f"Data exported to {timestamped_filename}")
    return timestamped_filename

def post_to_feishu(df, webhook_url, csrf_token=None, logger=None):
    """Post data to Feishu webhook - send each record individually"""
    try:
        # Mapping SQL Server columns to PostgreSQL columns (same as webhook)
        column_mapping = {
            'Alias': 'alias',
            'DeviceName': 'device_name',
            'IPAddress': 'ip_address',
            'OwnerID': 'owner_id',
            'SerialNumber': 'serial_number',
            'DomainName': 'domain_name',
            'LogonUser': 'logon_user',
            'Model': 'model',
            'SystemType': 'system_type',
            'AgentVersion': 'agent_version',
            'LastRespond': 'last_respond',
            'encrypted': 'encrypted',
            'GroupName': 'group_name',
            'ComputerType': 'computer_type',
            'FIRSTNAME': 'firstname',
            'LASTNAME': 'lastname',
            'ADDRESS': 'address',
            'Remark': 'remark',
            'MonitorType': 'monitor_type',
            'Answer': 'answer',
            'ResponseBy': 'response_by',
            'WindowOS': 'window_os',
            'WindowOSFull': 'window_os_full',
            'NessusAgent': 'nessus_agent',
            'AssetNumber': 'asset_number',
            'AgentID': 'agent_id',
            'StaffID': 'staff_id',
            'OverMonth': 'over_month'
        }
        
        # Rename columns in DataFrame
        df_mapped = df.rename(columns=column_mapping)
        
        # Convert DataFrame to records
        records = df_mapped.to_dict('records')
        
        # Print first record for debugging
        if logger:
            logger.debug(f"First record sample: {records[0] if records else 'No records'}")
        
        # Prepare headers
        headers = {
            'Content-Type': 'application/json'
        }
        
        # Add CSRF token to cookie if provided
        cookies = {}
        if csrf_token:
            cookies['_csrf_token'] = csrf_token
        
        success_count = 0
        error_count = 0
        
        for idx, record in enumerate(records):
            # Convert datetime objects to string and handle NaN
            processed_record = {}
            for key, value in record.items():
                if pd.isna(value):
                    processed_record[key] = None
                elif isinstance(value, (datetime, pd.Timestamp)):
                    processed_record[key] = value.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    processed_record[key] = value
            
            # Send POST request for each record
            try:
                response = requests.post(
                    webhook_url,
                    json=processed_record,
                    headers=headers,
                    cookies=cookies,
                    timeout=30
                )
                
                if response.status_code == 200:
                    success_count += 1
                    if (idx + 1) % 100 == 0:
                        if logger:
                            logger.info(f"Posted {idx + 1}/{len(records)} records to Feishu webhook")
                else:
                    error_count += 1
                    if logger:
                        logger.error(f"Failed to post record {idx + 1}. Status code: {response.status_code}")
                        logger.error(f"Response: {response.text}")
            except Exception as e:
                error_count += 1
                if logger:
                    logger.error(f"Error posting record {idx + 1}: {str(e)}")
        
        if logger:
            logger.info(f"Successfully posted {success_count}/{len(records)} records to Feishu webhook")
            if error_count > 0:
                logger.warning(f"Failed to post {error_count} records")
        
        return success_count > 0
    except Exception as e:
        if logger:
            logger.error(f"Error posting to Feishu webhook: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        return False

def main():
    # Setup logging
    logger, sql_logger = setup_logging()
    
    # SQL Query
    sql_query = """
SELECT         s.Alias,s.DeviceName,s.IPAddress,s.OwnerID,c.SerialNumber,c.DomainName,c.LogonUser,i.Model,'' AS SystemType,c.AgentVersion,s.LastRespond, '' AS encrypted
                ,g.GroupName,c.ComputerType,
                u.FIRSTNAME,u.LASTNAME,u.ADDRESS
                ,'' AS Remark,'' AS MonitorType, '' AS Answer, '' AS ResponseBy,
                o.Version AS WindowOS, o.VersionFull AS WindowOSFull,
                CASE WHEN ck.AgentID IS NULL THEN 'Not Install' ELSE 'Installed' END AS NessusAgent,
                s.AssetNumber,s.AgentID,e.FieldTxt1 as StaffID
                ,datediff(m,s.LastRespond,GETDATE()) AS OverMonth
FROM TB_SYSTEMDEVICE s (NOLOCK)
LEFT JOIN TB_COMPUTER c (NOLOCK) ON c.AgentID=s.AgentID
LEFT JOIN TB_INV_SYSTEM i (NOLOCK) ON i.AgentID=s.AgentID
LEFT JOIN TB_DEVICEGROUP g (NOLOCK) ON g.GroupId=s.GroupID
LEFT JOIN TB_USER u (NOLOCK) ON u.USER_ID=s.OwnerID  
LEFT JOIN TB_INV_OS o (NOLOCK)ON o.AgentID=s.AgentID
LEFT JOIN
(
        select distinct c.AgentID
        from [TB_COMPUTER] c 
        left join [TB_INV_APPLICATION] a on a.AgentID=c.AgentID
        LEFT JOIN [TB_SOFTWARE] s oN s.id=a.Id
        LEFT JOIN TB_SYSTEMDEVICE p ON p.AgentID=c.AgentID
        LEFT JOIN TB_INV_SYSTEM i ON i.AgentID=c.AgentID
        where s.SoftwareName like '%nessus%'
) ck ON ck.AgentID=s.AgentID
LEFT JOIN TB_Extention e ON e.AgentID=s.AgentID
where s.GroupID not in ('1')
          --and s.Alias in ('P20011501060640','N20011501060623','N20041501060678','N20011501060623')
order by s.GroupID,c.ComputerType
    """
    
    # Log SQL query
    sql_logger.info("="*80)
    sql_logger.info("SQL Query Executed:")
    sql_logger.info(sql_query)
    sql_logger.info("="*80)
    
    try:
        logger.info("Starting ASM Data Export Process")
        
        # Read configuration
        config = read_config(logger=logger)
        
        # Connect to SQL Server
        logger.info("Connecting to SQL Server...")
        sql_conn = connect_sql_server(config, logger)
        logger.info("Connected to SQL Server successfully")
        
        # Execute query
        logger.info("Executing SQL query...")
        df = execute_sql_query(sql_conn, sql_query, logger)
        logger.info(f"Retrieved {len(df)} rows from SQL Server")
        
        # Log data sample
        if len(df) > 0:
            logger.debug(f"First row data: {df.iloc[0].to_dict()}")
        
        # Close SQL Server connection
        sql_conn.close()
        logger.info("SQL Server connection closed")
        
        # Export to text file
        logger.info("Exporting to text file...")
        text_file = config['EXPORT']['txt_file']
        export_to_text(df, text_file, logger)
        
        # Export to Excel
        logger.info("Exporting to Excel...")
        excel_file = config['EXPORT']['excel_file']
        sheet_name = config['EXPORT']['sheet_name']
        export_to_excel(df, excel_file, sheet_name, logger)
        
        # Post to Feishu webhook if enabled
        webhook_enabled = config['WEBHOOK'].get('enabled', 'false').lower() == 'true'
        webhook_url = config['WEBHOOK'].get('url', '')
        
        logger.info(f"Webhook enabled: {webhook_enabled}")
        logger.info(f"Webhook URL configured: {bool(webhook_url)}")
        
        if webhook_enabled and webhook_url:
            logger.info("Posting to Feishu webhook...")
            csrf_token = config['WEBHOOK'].get('csrf_token', '')
            post_to_feishu(df, webhook_url, csrf_token, logger)
        else:
            logger.info("Webhook posting skipped (not enabled or no URL configured)")
        
        # Connect to PostgreSQL (optional - if fails, continue without it)
        try:
            logger.info("Connecting to PostgreSQL...")
            pg_conn = connect_postgresql(config, logger)
            logger.info("Connected to PostgreSQL successfully")
            
            # Create table and insert data
            table_name = config['POSTGRESQL']['table']
            logger.info(f"Verifying table {table_name} in PostgreSQL...")
            create_postgresql_table(pg_conn, df, table_name, logger)
            
            logger.info(f"Inserting data into PostgreSQL...")
            upsert_postgresql_data(pg_conn, df, table_name, logger)
            
            # Close PostgreSQL connection
            pg_conn.close()
            logger.info("PostgreSQL connection closed")
        except Exception as pg_error:
            logger.error(f"PostgreSQL export failed: {str(pg_error)}")
            import traceback
            logger.error(traceback.format_exc())
            logger.info("Continuing with text and Excel exports only...")
        
        logger.info("="*50)
        logger.info("Data export completed successfully!")
        logger.info("="*50)
        
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()
