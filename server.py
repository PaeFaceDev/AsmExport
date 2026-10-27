import configparser
import pyodbc
import psycopg2
import pandas as pd
from datetime import datetime
import os

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
    pg_required = ['host', 'port', 'database', 'username', 'password']
    for key in pg_required:
        if key not in config['POSTGRESQL']:
            raise ValueError(f"Missing required key '{key}' in [POSTGRESQL] section")
    
    # Optional table name with default
    if 'table' not in config['POSTGRESQL']:
        config['POSTGRESQL']['table'] = 'system_devices'
    
    # Validate EXPORT settings with defaults
    if 'txt_file' not in config['EXPORT']:
        config['EXPORT']['txt_file'] = 'output.txt'
    if 'excel_file' not in config['EXPORT']:
        config['EXPORT']['excel_file'] = 'output.xlsx'
    if 'sheet_name' not in config['EXPORT']:
        config['EXPORT']['sheet_name'] = 'Sheet1'
    
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
    """Create table in PostgreSQL if it doesn't exist"""
    cursor = pg_conn.cursor()
    
    # Generate column definitions based on DataFrame
    column_defs = []
    for col in df.columns:
        col_name = col.lower().replace(' ', '_')
        # Simple type mapping - can be improved
        col_defs.append(f"{col_name} TEXT")
    
    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id SERIAL PRIMARY KEY,
        {', '.join(column_defs)},
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    
    cursor.execute(create_table_sql)
    pg_conn.commit()
    print(f"Table {table_name} created/verified in PostgreSQL")

def insert_postgresql_data(pg_conn, df, table_name):
    """Insert data into PostgreSQL table"""
    cursor = pg_conn.cursor()
    
    # Convert column names to lowercase with underscores
    df.columns = [col.lower().replace(' ', '_') for col in df.columns]
    
    # Prepare insert statement
    columns = ', '.join(df.columns)
    placeholders = ', '.join(['%s'] * len(df.columns))
    insert_sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
    
    # Insert data in batches
    batch_size = 1000
    for i in range(0, len(df), batch_size):
        batch = df.iloc[i:i+batch_size]
        for _, row in batch.iterrows():
            cursor.execute(insert_sql, tuple(row))
        pg_conn.commit()
        print(f"Inserted {min(i+batch_size, len(df))} / {len(df)} rows")
    
    print(f"Successfully inserted {len(df)} rows into PostgreSQL")

def ensure_directory_exists(filename):
    """Create directory if it doesn't exist"""
    directory = os.path.dirname(filename)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created directory: {directory}")

def export_to_text(df, filename):
    """Export DataFrame to text file"""
    ensure_directory_exists(filename)
    df.to_csv(filename, sep='\t', index=False, encoding='utf-8')
    print(f"Data exported to {filename}")

def export_to_excel(df, filename, sheet_name):
    """Export DataFrame to Excel file"""
    ensure_directory_exists(filename)
    df.to_excel(filename, sheet_name=sheet_name, index=False, engine='openpyxl')
    print(f"Data exported to {filename}")

def main():
    # SQL Query
    sql_query = """
    SELECT s.Alias,s.DeviceName,s.IPAddress,s.OwnerID,c.SerialNumber,c.DomainName,c.LogonUser,i.Model,'' AS SystemType,c.AgentVersion,s.LastRespond, '' AS encrypted ,g.GroupName,c.ComputerType, u.FIRSTNAME,u.LASTNAME,u.ADDRESS ,'' AS Remark,'' AS MonitorType, '' AS Answer, '' AS ResponseBy, o.Version AS WindowOS, o.VersionFull AS WindowOSFull, CASE WHEN ck.AgentID IS NULL THEN 'Not Install' ELSE 'Installed' END AS NessusAgent, s.AssetNumber,s.AgentID,e.FieldTxt1 as StaffID ,datediff(m,s.LastRespond,GETDATE()) AS OverMonth 
    FROM TB_SYSTEMDEVICE s (NOLOCK) 
    LEFT JOIN TB_COMPUTER c (NOLOCK) ON c.AgentID=s.AgentID 
    LEFT JOIN TB_INV_SYSTEM i (NOLOCK) ON i.AgentID=s.AgentID 
    LEFT JOIN TB_DEVICEGROUP g (NOLOCK) ON g.GroupId=s.GroupID 
    LEFT JOIN TB_USER u (NOLOCK) ON u.USER_ID=s.OwnerID 
    LEFT JOIN TB_INV_OS o (NOLOCK)ON o.AgentID=s.AgentID 
    LEFT JOIN ( 
        select distinct c.AgentID from [TB_COMPUTER] c 
        left join [TB_INV_APPLICATION] a on a.AgentID=c.AgentID 
        LEFT JOIN [TB_SOFTWARE] s ON s.id=a.Id 
        LEFT JOIN TB_SYSTEMDEVICE p ON p.AgentID=c.AgentID 
        LEFT JOIN TB_INV_SYSTEM i ON i.AgentID=c.AgentID 
        where s.SoftwareName like '%nessus%' 
    ) ck ON ck.AgentID=s.AgentID 
    LEFT JOIN TB_Extention e ON e.AgentID=s.AgentID 
    where s.GroupID not in ('1') 
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
        
        # Connect to PostgreSQL (optional - if fails, continue without it)
        try:
            print("\nConnecting to PostgreSQL...")
            pg_conn = connect_postgresql(config)
            print("Connected to PostgreSQL")
            
            # Create table and insert data
            table_name = config['POSTGRESQL']['table']
            print(f"\nCreating table {table_name} in PostgreSQL...")
            create_postgresql_table(pg_conn, df, table_name)
            
            print(f"\nInserting data into PostgreSQL...")
            insert_postgresql_data(pg_conn, df, table_name)
            
            # Close PostgreSQL connection
            pg_conn.close()
        except Exception as pg_error:
            print(f"\nWarning: PostgreSQL export failed: {str(pg_error)}")
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
