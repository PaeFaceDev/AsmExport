# SQL Server Data Export Tool

This tool connects to a SQL Server database, executes a predefined query, and exports the data to PostgreSQL, text file, and Excel file.

## Features

- Connects to SQL Server using pyodbc
- Executes complex SQL query with multiple JOINs
- Exports data to PostgreSQL database
- Exports data to tab-delimited text file
- Exports data to Excel file with customizable sheet name
- Configuration via conf.ini file

## Prerequisites

- Python 3.7+
- SQL Server ODBC Driver (ODBC Driver 17 for SQL Server recommended)
- PostgreSQL server

## Installation

1. Install the required Python packages:

```bash
pip install -r requirements.txt
```

Or using the virtual environment:

```bash
env/Scripts/pip install -r requirements.txt
```

## Configuration

1. Copy `conf.ini.example` to `conf.ini`:

```bash
copy conf.ini.example conf.ini
```

2. Edit `conf.ini` with your database credentials:

```ini
[SQL_SERVER]
server = YOUR_SQL_SERVER_HOST
database = YOUR_DATABASE_NAME
username = YOUR_SQL_USERNAME
password = YOUR_SQL_PASSWORD
driver = ODBC Driver 17 for SQL Server

[POSTGRESQL]
host = YOUR_POSTGRES_HOST
port = 5432
database = YOUR_POSTGRES_DATABASE
username = YOUR_POSTGRES_USERNAME
password = YOUR_POSTGRES_PASSWORD
table = system_devices

[EXPORT]
text_file = output.txt
excel_file = output.xlsx
sheet_name = SystemDevices
```

### Configuration Sections

- **SQL_SERVER**: Connection details for the source SQL Server database
- **POSTGRESQL**: Connection details for the target PostgreSQL database
- **EXPORT**: Output file names and Excel sheet name

## Usage

Run the script:

```bash
python server.py
```

Or using the virtual environment:

```bash
env/Scripts/python server.py
```

## What the Script Does

1. Reads configuration from `conf.ini`
2. Connects to SQL Server
3. Executes the predefined SQL query
4. Exports data to text file (tab-delimited)
5. Exports data to Excel file
6. Connects to PostgreSQL
7. Creates table if it doesn't exist
8. Inserts data into PostgreSQL table
9. Closes all connections

## SQL Query

The script uses the following SQL query to fetch data:

```sql
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
```

## Output Files

- **output.txt**: Tab-delimited text file with all query results
- **output.xlsx**: Excel file with query results in a single sheet
- **PostgreSQL table**: Data inserted into the configured PostgreSQL table

## Troubleshooting

### SQL Server Connection Issues

- Ensure ODBC Driver 17 for SQL Server is installed
- Verify SQL Server credentials and server address
- Check if SQL Server allows remote connections

### PostgreSQL Connection Issues

- Verify PostgreSQL server is running
- Check firewall settings
- Ensure the specified database exists

### Import Errors

- Make sure all required packages are installed
- Check Python version compatibility

## Dependencies

- pyodbc: SQL Server connectivity
- psycopg2-binary: PostgreSQL connectivity
- pandas: Data manipulation
- openpyxl: Excel file writing

## Security Notes

- `conf.ini` is in `.gitignore` to prevent committing sensitive credentials
- Never commit `conf.ini` to version control
- Use environment variables for production deployments
