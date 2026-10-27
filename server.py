import configparser
import pyodbc
import psycopg2
import pandas as pd
from datetime import datetime
import os
import requests
import json

def read_config(config_file='conf.ini'):
    """Read configuration from conf.ini file"""
    config = configparser.ConfigParser()
    config.read(config_file)
    
    # Validate required sections
    required_sections = ['SQLSERVER', 'POSTGRESQL', 'EXPORT']
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required section [{section}] in configuration file")
    
    # Validate SQLSERVER settings
    sql_required = ['server', 'database', 'username', 'password', 'driver']
    for key in sql_required:
        if key not in config['SQLSERVER']:
            raise ValueError(f"Missing required key '{key}' in [SQLSERVER] section")
    
    # Validate POSTGRESQL settings
    pg_required = ['host', 'port', 'username', 'password']
    for key in pg_required:
        if key not in config['POSTGRESQL']:
            raise ValueError(f"Missing required key '{key}' in [POSTGRESQL] section")
    
    # Optional database name with default
    if 'database' not in config['POSTGRESQL']:
        config['POSTGRESQL']['database'] = 'linebot'
    
    # Optional table name with default
    if 'table' not in config['POSTGRESQL']:
        config['POSTGRESQL']['table'] = 'asm_data'
    
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
    
    return config

def connect_sql_server(config):
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
    return pyodbc.connect(connection_string)

def connect_postgresql(config):
    """Connect to PostgreSQL"""
    pg_config = config['POSTGRESQL']
    return psycopg2.connect(
        host=pg_config['host'],
        port=pg_config['port'],
        database=pg_config['database'],
        user=pg_config['username'],
        password=pg_config['password']
    )

def execute_sql_query(sql_conn, query):
    """Execute SQL query and return data as DataFrame"""
    cursor = sql_conn.cursor()
    cursor.execute(query)
    columns = [column[0] for column in cursor.description]
    data = cursor.fetchall()
    df = pd.DataFrame.from_records(data, columns=columns)
    return df

def create_postgresql_table(pg_conn, df, table_name):
    """Create or recreate table in PostgreSQL with proper schema"""
    cursor = pg_conn.cursor()
    
    # Drop existing table if it exists
    print(f"Dropping existing table {table_name} if exists...")
    cursor.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
    cursor.execute(f"DROP SEQUENCE IF EXISTS {table_name}_id_seq CASCADE")
    pg_conn.commit()
    
    # Create sequence
    print(f"Creating sequence {table_name}_id_seq...")
    cursor.execute(f"CREATE SEQUENCE {table_name}_id_seq")
    pg_conn.commit()
    
    # Create table with proper schema
    print(f"Creating table {table_name}...")
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
    print(f"Creating indexes...")
    cursor.execute(f"CREATE INDEX idx_{table_name}_agent_id ON {table_name}(agent_id)")
    cursor.execute(f"CREATE INDEX idx_{table_name}_device_name ON {table_name}(device_name)")
    pg_conn.commit()
    
    print(f"Table {table_name} created successfully with UNIQUE constraint on device_name")

def upsert_postgresql_data(pg_conn, df, table_name):
    """Insert or update data in PostgreSQL table using device_name as key"""
    cursor = pg_conn.cursor()
    
    # Convert column names to match PostgreSQL table (device_name, ip_address, etc.)
    original_columns = df.columns.tolist()
    print(f"Original columns from SQL Server: {original_columns}")
    
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
    print(f"Converted columns: {df.columns.tolist()}")
    
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
    
    print(f"UPSERT SQL prepared with {len(columns)} columns")
    
    # Check which device_names already exist
    device_names = df['device_name'].tolist()
    print(f"Total device_names to process: {len(device_names)}")
    print(f"Sample device_names: {device_names[:5]}")
    
    if device_names:
        # Filter out None values
        valid_device_names = [dn for dn in device_names if dn is not None and dn != '']
        print(f"Valid device_names (not None/empty): {len(valid_device_names)}")
        
        if valid_device_names:
            check_sql = f"SELECT device_name FROM {table_name} WHERE device_name = ANY(%s)"
            cursor.execute(check_sql, (valid_device_names,))
            existing_devices = set(row[0] for row in cursor.fetchall())
            print(f"Existing devices in database: {len(existing_devices)}")
        else:
            existing_devices = set()
            print("No valid device_names found")
    else:
        existing_devices = set()
        print("No device_names found in data")
    
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
                    print(f"\nError processing row {idx} for device {device_name}: {str(e)}")
                    print(f"Columns: {columns}")
                    print(f"Row data length: {len(row_data)}")
                    print(f"Row data: {row_data[:5]}...")  # Show first 5 values
                    import traceback
                    traceback.print_exc()
                elif error_count == 4:
                    print("\nSuppressing further error details (too many errors)...")
                pg_conn.rollback()
        
        pg_conn.commit()
        print(f"Processed {min(i+batch_size, len(df))} / {len(df)} rows")
    
    if error_count > 0:
        print(f"\nWarning: {error_count} rows had errors during processing")
    
    print(f"Successfully processed {len(df)} rows in PostgreSQL")
    print(f"  - Inserted: {insert_count}")
    print(f"  - Updated: {update_count}")

def ensure_directory_exists(filename):
    """Create directory if it doesn't exist"""
    directory = os.path.dirname(filename)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created directory: {directory}")

def export_to_text(df, filename):
    """Export DataFrame to text file with timestamp"""
    # Generate timestamp in yyyyMMddHHmmss format
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    
    # Insert timestamp before file extension
    base, ext = os.path.splitext(filename)
    timestamped_filename = f"{base}_{timestamp}{ext}"
    
    ensure_directory_exists(timestamped_filename)
    df.to_csv(timestamped_filename, sep='\t', index=False, encoding='utf-8')
    print(f"Data exported to {timestamped_filename}")
    return timestamped_filename

def export_to_excel(df, filename, sheet_name):
    """Export DataFrame to Excel file with timestamp"""
    # Generate timestamp in yyyyMMddHHmmss format
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    
    # Insert timestamp before file extension
    base, ext = os.path.splitext(filename)
    timestamped_filename = f"{base}_{timestamp}{ext}"
    
    ensure_directory_exists(timestamped_filename)
    df.to_excel(timestamped_filename, sheet_name=sheet_name, index=False, engine='openpyxl')
    print(f"Data exported to {timestamped_filename}")
    return timestamped_filename

def post_to_feishu(df, webhook_url, csrf_token=None):
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
        print(f"First record sample: {records[0] if records else 'No records'}")
        
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
                        print(f"Posted {idx + 1}/{len(records)} records to Feishu webhook")
                else:
                    error_count += 1
                    print(f"Failed to post record {idx + 1}. Status code: {response.status_code}")
                    print(f"Response: {response.text}")
            except Exception as e:
                error_count += 1
                print(f"Error posting record {idx + 1}: {str(e)}")
        
        print(f"Successfully posted {success_count}/{len(records)} records to Feishu webhook")
        if error_count > 0:
            print(f"Failed to post {error_count} records")
        
        return success_count > 0
    except Exception as e:
        print(f"Error posting to Feishu webhook: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
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
    
    try:
        # Read configuration
        config = read_config()
        print("Configuration loaded successfully")
        
        # Connect to SQL Server
        print("Connecting to SQL Server...")
        sql_conn = connect_sql_server(config)
        print("Connected to SQL Server")
        
        # Execute query
        print("Executing SQL query...")
        df = execute_sql_query(sql_conn, sql_query)
        print(f"Retrieved {len(df)} rows from SQL Server")
        
        # Close SQL Server connection
        sql_conn.close()
        
        # Export to text file
        print("\nExporting to text file...")
        text_file = config['EXPORT']['txt_file']
        export_to_text(df, text_file)
        
        # Export to Excel
        print("\nExporting to Excel...")
        excel_file = config['EXPORT']['excel_file']
        sheet_name = config['EXPORT']['sheet_name']
        export_to_excel(df, excel_file, sheet_name)
        
        # Post to Feishu webhook if enabled
        webhook_enabled = config['WEBHOOK'].get('enabled', 'false').lower() == 'true'
        webhook_url = config['WEBHOOK'].get('url', '')
        
        print(f"\nWebhook enabled: {webhook_enabled}")
        print(f"Webhook URL configured: {bool(webhook_url)}")
        
        if webhook_enabled and webhook_url:
            print("Posting to Feishu webhook...")
            csrf_token = config['WEBHOOK'].get('csrf_token', '')
            post_to_feishu(df, webhook_url, csrf_token)
        else:
            print("Webhook posting skipped (not enabled or no URL configured)")
        
        # Connect to PostgreSQL (optional - if fails, continue without it)
        try:
            print("\nConnecting to PostgreSQL...")
            pg_conn = connect_postgresql(config)
            print("Connected to PostgreSQL")
            
            # Create table and insert data
            table_name = config['POSTGRESQL']['table']
            print(f"\nVerifying table {table_name} in PostgreSQL...")
            create_postgresql_table(pg_conn, df, table_name)
            
            print(f"\nInserting data into PostgreSQL...")
            upsert_postgresql_data(pg_conn, df, table_name)
            
            # Close PostgreSQL connection
            pg_conn.close()
            print("PostgreSQL connection closed")
        except Exception as pg_error:
            print(f"\nWarning: PostgreSQL export failed: {str(pg_error)}")
            import traceback
            traceback.print_exc()
            print("Continuing with text and Excel exports only...")
        
        print("\n" + "="*50)
        print("Data export completed successfully!")
        print("="*50)
        
    except Exception as e:
        print(f"\nError occurred: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
