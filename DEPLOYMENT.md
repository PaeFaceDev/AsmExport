# ASM Export - Deployment Guide

## สิ่งที่ต้องใช้ร่วมกับ exe

เมื่อนำ exe ไปใช้ที่เครื่องอื่น ต้องนำไฟล์เหล่านี้ไปด้วย:

### ไฟล์ที่จำเป็น:
1. **asm_export.exe** - ไฟล์โปรแกรมหลัก (อยู่ใน folder `dist/`)
2. **conf.ini** - ไฟล์ configuration (ต้องสร้างจาก conf.ini.example)

### วิธีติดตั้ง:

1. สร้าง folder ใหม่บนเครื่องเป้าหมาย
2. คัดลอกไฟล์ `asm_export.exe` ไปยัง folder นั้น
3. คัดลอกไฟล์ `conf.ini.example` แล้วเปลี่ยนชื่อเป็น `conf.ini`
4. แก้ไข `conf.ini` ใส่ค่า configuration จริง:
   - SQL Server connection
   - PostgreSQL connection
   - Webhook settings (ถ้าต้องการใช้)

## วิธีใช้งาน

### 1. เตรียม Configuration

สร้างไฟล์ `conf.ini` จาก `conf.ini.example`:

```ini
[SQLSERVER]
server = YOUR_SQL_SERVER_HOST
database = YOUR_DATABASE_NAME
username = YOUR_SQL_USERNAME
password = YOUR_SQL_PASSWORD
driver = ODBC Driver 18 for SQL Server

[POSTGRESQL]
host = YOUR_POSTGRES_HOST
port = 5432
database = linebot
username = YOUR_POSTGRES_USERNAME
password = YOUR_POSTGRES_PASSWORD
table = asm_data

[EXPORT]
txt_file = output.txt
excel_file = output.xlsx
sheet_name = SystemDevices

[WEBHOOK]
enabled = true
url = https://ihaier.feishu.cn/base/automation/webhook/event/UqbCaf5GVwO6m9hnpGIchl3onBh
csrf_token = YOUR_CSRF_TOKEN
```

### 2. รันโปรแกรม

Double-click ที่ `asm_export.exe` หรือรันผ่าน command line:

```bash
asm_export.exe
```

### 3. Output

โปรแกรมจะสร้าง:
- **output/** - Text และ Excel files (พร้อม timestamp)
- **logs/** - Log files สำหรับวิเคราะห์

## การติดตั้ง SQL Server ODBC Driver

บนเครื่องที่จะรัน exe ต้องติดตั้ง:
- **ODBC Driver 18 for SQL Server** (หรือ 17)

ดาวน์โหลดจาก: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server

## Schedule อัตโนมัติ (Windows Task Scheduler)

### วิธีตั้งค่า:

1. เปิด **Task Scheduler**
2. คลิก **Create Task**
3. **General**:
   - Name: ASM Data Export
   - Select: Run whether user is logged on or not
4. **Triggers**:
   - New Trigger
   - Select: Daily
   - Set time: เช่น 08:00 AM
5. **Actions**:
   - New Action
   - Program/Script: เลือก path ของ `asm_export.exe`
   - Start in: เลือก folder ที่เก็บ exe
6. **OK** บันทึก

## การแก้ปัญหา

### exe ไม่ทำงาน:
1. ตรวจสอบว่า `conf.ini` อยู่ใน folder เดียวกับ exe
2. ตรวจสอบ ODBC Driver ติดตั้งหรือไม่
3. ดู log files ใน folder `logs/`

### Connection Error:
1. ตรวจสอบ configuration ใน conf.ini
2. ตรวจสอบ network/firewall
3. ดู log files สำหรับ error details

## ไฟล์ที่สร้างขึ้นหลังรัน:

- `logs/asm_export_YYYYMMDD_HHMMSS.log` - Log ทั้งหมด
- `logs/sql_queries_YYYYMMDD_HHMMSS.log` - SQL queries
- `output/data_YYYYMMDD_HHMMSS.txt` - Text file export
- `output/data_YYYYMMDD_HHMMSS.xlsx` - Excel file export

## ข้อควรระวัง:

- exe จะสร้าง folder `logs/` และ `output/` อัตโนมัติ
- ต้องมีสิทธิ์เขียนไฟล์ใน folder ที่รัน exe
- ข้อมูลใน PostgreSQL table จะถูกลบและสร้างใหม่ทุกครั้ง
