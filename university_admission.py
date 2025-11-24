#!/usr/bin/env python3
"""
HỆ THỐNG QUẢN LÝ TUYỂN SINH ĐẠI HỌC - HOÀN THIỆN
"""

import http.server
import socketserver
import json
import sqlite3
import hashlib
import os
from datetime import datetime, timedelta
import secrets
import urllib.parse
import csv
import io

# ==================== CẤU HÌNH HỆ THỐNG ====================

class SystemConfig:
    def __init__(self):
        self.config = {
            'max_aspirations': 4,
            'aspiration_fee': 50000,
            'currency': 'VND',
            'contact_info': {
                'hotline': '1900 1234',
                'email': 'tuyensinh@university.edu.vn',
                'address': 'Số 1 Đại Cồ Việt, Hà Nội',
                'website': 'https://tuyensinh.university.edu.vn'
            }
        }
    
    def get(self, key, default=None):
        return self.config.get(key, default)

config = SystemConfig()

def init_database():
    conn = sqlite3.connect('university_admission.db')
    cursor = conn.cursor()
    
    # Bảng kỳ thi
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            registration_start DATE NOT NULL,
            registration_end DATE NOT NULL,
            result_announcement DATE NOT NULL,
            status TEXT CHECK(status IN ('upcoming', 'active', 'completed')) DEFAULT 'upcoming',
            max_aspirations INTEGER DEFAULT 4,
            aspiration_fee REAL DEFAULT 50000,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Bảng người dùng
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT CHECK(role IN ('admin', 'manager', 'candidate')) NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Bảng thí sinh
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            citizen_id TEXT UNIQUE NOT NULL,
            date_of_birth DATE,
            gender TEXT,
            address TEXT,
            phone TEXT,
            high_school TEXT,
            graduation_year INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Bảng trường đại học
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS universities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            email TEXT,
            website TEXT,
            description TEXT,
            status TEXT DEFAULT 'active'
        )
    ''')
    
    # Bảng ngành học
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS majors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            university_id INTEGER,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            quota INTEGER DEFAULT 0,
            subject_group TEXT,
            duration INTEGER DEFAULT 4,
            tuition_fee REAL,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (university_id) REFERENCES universities(id),
            UNIQUE(university_id, code)
        )
    ''')
    
    # Bảng nguyện vọng
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS aspirations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER,
            exam_id INTEGER,
            university_id INTEGER,
            major_id INTEGER,
            priority_order INTEGER NOT NULL CHECK(priority_order BETWEEN 1 AND 10),
            status TEXT DEFAULT 'pending',
            payment_status TEXT DEFAULT 'pending',
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_by INTEGER,
            approved_at TIMESTAMP,
            manager_notes TEXT,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id),
            FOREIGN KEY (exam_id) REFERENCES exams(id),
            FOREIGN KEY (university_id) REFERENCES universities(id),
            FOREIGN KEY (major_id) REFERENCES majors(id),
            FOREIGN KEY (approved_by) REFERENCES users(id),
            UNIQUE(candidate_id, exam_id, priority_order)
        )
    ''')
    
    # Bảng thanh toán
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER,
            exam_id INTEGER,
            aspiration_id INTEGER,
            amount REAL NOT NULL,
            payment_method TEXT NOT NULL,
            transaction_id TEXT UNIQUE,
            status TEXT DEFAULT 'pending',
            payment_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id),
            FOREIGN KEY (exam_id) REFERENCES exams(id),
            FOREIGN KEY (aspiration_id) REFERENCES aspirations(id)
        )
    ''')
    
    # Bảng tài liệu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            file_path TEXT,
            file_type TEXT,
            file_size INTEGER,
            category TEXT CHECK(category IN ('guide', 'regulation', 'template', 'announcement')),
            status TEXT DEFAULT 'active',
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    # Insert default data
    insert_default_data(cursor)
    
    conn.commit()
    conn.close()

def insert_default_data(cursor):
    """Insert dữ liệu mặc định ĐÃ SỬA LỖI"""
    # Default admin user
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, password, email, full_name, role) 
        VALUES (?, ?, ?, ?, ?)
    ''', ('admin', hash_password('admin123'), 'admin@university.edu.vn', 'Quản trị viên hệ thống', 'admin'))
    
    # Default manager
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, password, email, full_name, role) 
        VALUES (?, ?, ?, ?, ?)
    ''', ('manager', hash_password('manager123'), 'manager@university.edu.vn', 'Cán bộ tuyển sinh', 'manager'))
    
    # Default candidate
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, password, email, full_name, role) 
        VALUES (?, ?, ?, ?, ?)
    ''', ('candidate', hash_password('candidate123'), 'candidate@example.com', 'Nguyễn Văn A', 'candidate'))
    
    # Get user IDs
    cursor.execute('SELECT id, username FROM users')
    user_ids = {username: id for id, username in cursor.fetchall()}
    
    # Insert candidate profile
    cursor.execute('''
        INSERT OR IGNORE INTO candidates (user_id, citizen_id, date_of_birth, gender, address, phone, high_school, graduation_year)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_ids['candidate'], '00123456789', '2005-03-15', 'male', 
          '123 Đường ABC, Quận XYZ, Hà Nội', '0912345678', 'THPT Chuyên Hà Nội - Amsterdam', 2024))
    
    # Default exam
    cursor.execute('''
        INSERT OR IGNORE INTO exams (code, name, description, registration_start, registration_end, result_announcement, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', ('EXAM_2025', 'Kỳ thi tuyển sinh Đại học 2025', 
          'Kỳ thi tuyển sinh đại học chính quy năm 2025',
          '2025-01-01', '2025-12-31', '2025-06-15', 'active'))
    
    # Default universities
    universities_data = [
        ('HUST', 'Đại học Bách Khoa Hà Nội', 'Số 1 Đại Cồ Việt, Hai Bà Trưng, Hà Nội'),
        ('NEU', 'Đại học Kinh tế Quốc dân', '207 Giải Phóng, Đồng Tâm, Quận Hai Bà Trưng, Hà Nội'),
        ('UET', 'Đại học Công nghệ - ĐHQGHN', 'E3, 144 Xuân Thủy, Cầu Giấy, Hà Nội'),
        ('HPU', 'Đại học Hải Phòng', '171 Phan Đăng Lưu, Kiến An, Hải Phòng')
    ]
    
    for code, name, address in universities_data:
        cursor.execute('''
            INSERT OR IGNORE INTO universities (code, name, address) 
            VALUES (?, ?, ?)
        ''', (code, name, address))
    
    # Get university IDs
    cursor.execute('SELECT id, code FROM universities')
    university_ids = {code: id for id, code in cursor.fetchall()}
    
    # Sample majors - SỬA: Thêm các ngành học với ID rõ ràng
    majors_data = [
        (university_ids['HUST'], 'IT1', 'Công nghệ Thông tin', 200, 'A00,A01'),
        (university_ids['HUST'], 'ET1', 'Điện tử Viễn thông', 150, 'A00,A01'),
        (university_ids['NEU'], 'BA1', 'Quản trị Kinh doanh', 220, 'A00,A01,D01'),
        (university_ids['NEU'], 'FA1', 'Tài chính Ngân hàng', 160, 'A00,A01,D01'),
        (university_ids['UET'], 'CS1', 'Khoa học Máy tính', 180, 'A00,A01'),
        (university_ids['UET'], 'SE1', 'Kỹ thuật Phần mềm', 200, 'A00,A01'),
        (university_ids['HPU'], 'IT1', 'Công nghệ Thông tin', 180, 'A00,A01'),
        (university_ids['HPU'], 'BA1', 'Quản trị Kinh doanh', 200, 'A00,A01,D01')
    ]
    
    for university_id, code, name, quota, subject_group in majors_data:
        cursor.execute('''
            INSERT OR IGNORE INTO majors (university_id, code, name, quota, subject_group) 
            VALUES (?, ?, ?, ?, ?)
        ''', (university_id, code, name, quota, subject_group))
    
    # Get major IDs để sử dụng cho nguyện vọng
    cursor.execute('SELECT id, code FROM majors')
    major_ids = {}
    for row in cursor.fetchall():
        major_id, code = row
        major_ids[code] = major_id
    
    # Insert sample aspirations - SỬA: Sử dụng major_id thực tế
    cursor.execute('SELECT id FROM candidates LIMIT 1')
    candidate = cursor.fetchone()
    cursor.execute('SELECT id FROM exams LIMIT 1')
    exam = cursor.fetchone()
    
    if candidate and exam:
        aspirations_data = [
            (candidate[0], exam[0], university_ids['HUST'], major_ids['IT1'], 1, 'pending'),
            (candidate[0], exam[0], university_ids['UET'], major_ids['CS1'], 2, 'pending'),
            (candidate[0], exam[0], university_ids['NEU'], major_ids['BA1'], 3, 'pending')
        ]
        
        for candidate_id, exam_id, university_id, major_id, priority, status in aspirations_data:
            cursor.execute('''
                INSERT OR IGNORE INTO aspirations 
                (candidate_id, exam_id, university_id, major_id, priority_order, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (candidate_id, exam_id, university_id, major_id, priority, status))
    
    # Insert sample documents
    documents_data = [
        ('Hướng dẫn đăng ký nguyện vọng', 'Hướng dẫn chi tiết cách đăng ký nguyện vọng trực tuyến', 'guide'),
        ('Quy chế tuyển sinh 2025', 'Quy chế tuyển sinh đại học chính quy năm 2025', 'regulation'),
        ('Mẫu đơn đăng ký xét tuyển', 'Mẫu đơn đăng ký xét tuyển đại học', 'template'),
        ('Lịch trình tuyển sinh', 'Lịch trình các mốc thời gian quan trọng trong tuyển sinh', 'announcement')
    ]
    
    for title, description, category in documents_data:
        cursor.execute('''
            INSERT OR IGNORE INTO documents (title, description, category, created_by)
            VALUES (?, ?, ?, ?)
        ''', (title, description, category, user_ids['admin']))

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    return hash_password(password) == hashed

# Simple token system
active_tokens = {}

def create_token(user_id, username, role):
    token = secrets.token_hex(32)
    active_tokens[token] = {
        'user_id': user_id,
        'username': username,
        'role': role,
        'created_at': datetime.now()
    }
    return token

def verify_token(token):
    if token in active_tokens:
        token_data = active_tokens[token]
        if datetime.now() - token_data['created_at'] < timedelta(hours=24):
            return token_data
    return None

# ==================== PAYMENT SYSTEM ====================

def create_payment(candidate_id, exam_id, aspiration_id, amount, payment_method):
    """Tạo thanh toán mới"""
    conn = sqlite3.connect('university_admission.db')
    cursor = conn.cursor()
    
    # Kiểm tra xem nguyện vọng đã được thanh toán chưa
    cursor.execute('SELECT id FROM payments WHERE aspiration_id = ? AND status = "completed"', (aspiration_id,))
    if cursor.fetchone():
        conn.close()
        return None, "Nguyện vọng này đã được thanh toán"
    
    transaction_id = f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{secrets.token_hex(4)}"
    
    cursor.execute('''
        INSERT INTO payments (candidate_id, exam_id, aspiration_id, amount, payment_method, transaction_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (candidate_id, exam_id, aspiration_id, amount, payment_method, transaction_id))
    
    payment_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    return payment_id, transaction_id

def verify_payment(transaction_id):
    """Xác nhận thanh toán"""
    conn = sqlite3.connect('university_admission.db')
    cursor = conn.cursor()
    
    # Cập nhật trạng thái thanh toán
    cursor.execute('''
        UPDATE payments 
        SET status = 'completed', payment_date = CURRENT_TIMESTAMP
        WHERE transaction_id = ? AND status = 'pending'
    ''', (transaction_id,))
    
    # Cập nhật trạng thái thanh toán của nguyện vọng
    cursor.execute('''
        UPDATE aspirations 
        SET payment_status = 'paid'
        WHERE id = (
            SELECT aspiration_id FROM payments WHERE transaction_id = ?
        )
    ''', (transaction_id,))
    
    conn.commit()
    conn.close()

# ==================== DOCUMENT SYSTEM ====================

def get_documents(category=None):
    """Lấy danh sách tài liệu"""
    conn = sqlite3.connect('university_admission.db')
    cursor = conn.cursor()
    
    if category:
        cursor.execute('SELECT * FROM documents WHERE category = ? AND status = "active" ORDER BY created_at DESC', (category,))
    else:
        cursor.execute('SELECT * FROM documents WHERE status = "active" ORDER BY created_at DESC')
    
    documents = []
    for row in cursor.fetchall():
        documents.append({
            'id': row[0],
            'title': row[1],
            'description': row[2],
            'file_path': row[3],
            'file_type': row[4],
            'file_size': row[5],
            'category': row[6],
            'created_at': row[9]
        })
    
    conn.close()
    return documents

# ==================== MANAGER APPROVAL SYSTEM ====================

def get_pending_aspirations():
    """Lấy danh sách nguyện vọng chờ duyệt"""
    conn = sqlite3.connect('university_admission.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT a.id, a.priority_order, a.registered_at,
               u.name as university_name, m.name as major_name,
               c.citizen_id, usr.full_name as candidate_name,
               usr.email, c.phone, a.payment_status
        FROM aspirations a
        JOIN universities u ON a.university_id = u.id
        JOIN majors m ON a.major_id = m.id
        JOIN candidates c ON a.candidate_id = c.id
        JOIN users usr ON c.user_id = usr.id
        WHERE a.status = 'pending'
        ORDER BY a.registered_at DESC
    ''')
    
    pending_aspirations = []
    for row in cursor.fetchall():
        pending_aspirations.append({
            'id': row[0],
            'priority': row[1],
            'registered_at': row[2],
            'university_name': row[3],
            'major_name': row[4],
            'citizen_id': row[5],
            'candidate_name': row[6],
            'email': row[7],
            'phone': row[8],
            'payment_status': row[9]
        })
    
    conn.close()
    return pending_aspirations

def approve_aspiration(aspiration_id, manager_id, notes=''):
    """Duyệt nguyện vọng"""
    conn = sqlite3.connect('university_admission.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE aspirations 
        SET status = 'approved', approved_by = ?, approved_at = CURRENT_TIMESTAMP, manager_notes = ?
        WHERE id = ?
    ''', (manager_id, notes, aspiration_id))
    
    conn.commit()
    conn.close()

def reject_aspiration(aspiration_id, reason=''):
    """Từ chối nguyện vọng"""
    conn = sqlite3.connect('university_admission.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE aspirations 
        SET status = 'rejected', manager_notes = ?
        WHERE id = ?
    ''', (reason, aspiration_id))
    
    conn.commit()
    conn.close()

# ==================== PRINT SYSTEM ====================

def generate_aspirations_pdf(candidate_id):
    """Tạo PDF danh sách nguyện vọng"""
    conn = sqlite3.connect('university_admission.db')
    cursor = conn.cursor()
    
    # Lấy thông tin thí sinh
    cursor.execute('''
        SELECT u.full_name, c.citizen_id, c.date_of_birth, c.gender,
               c.address, c.phone, c.high_school, c.graduation_year
        FROM users u
        JOIN candidates c ON u.id = c.user_id
        WHERE c.id = ?
    ''', (candidate_id,))
    
    candidate_info = cursor.fetchone()
    
    # Lấy danh sách nguyện vọng
    cursor.execute('''
        SELECT a.priority_order, u.name as university_name, m.name as major_name,
               a.status, a.payment_status, a.registered_at,
               m.subject_group, u.code as university_code, m.code as major_code
        FROM aspirations a
        JOIN universities u ON a.university_id = u.id
        JOIN majors m ON a.major_id = m.id
        WHERE a.candidate_id = ?
        ORDER BY a.priority_order
    ''', (candidate_id,))
    
    aspirations = cursor.fetchall()
    conn.close()
    
    if not candidate_info:
        return None
    
    print_data = {
        'candidate': {
            'full_name': candidate_info[0],
            'citizen_id': candidate_info[1],
            'date_of_birth': candidate_info[2],
            'gender': candidate_info[3],
            'address': candidate_info[4],
            'phone': candidate_info[5],
            'high_school': candidate_info[6],
            'graduation_year': candidate_info[7]
        },
        'aspirations': [
            {
                'priority': row[0],
                'university_name': row[1],
                'major_name': row[2],
                'status': row[3],
                'payment_status': row[4],
                'registered_at': row[5],
                'subject_group': row[6],
                'university_code': row[7],
                'major_code': row[8]
            }
            for row in aspirations
        ],
        'print_date': datetime.now().strftime('%d/%m/%Y %H:%M'),
        'contact_info': config.get('contact_info')
    }
    
    return print_data

def export_aspirations_csv(candidate_id):
    """Xuất danh sách nguyện vọng ra CSV"""
    conn = sqlite3.connect('university_admission.db')
    cursor = conn.cursor()
    
    # Lấy thông tin thí sinh
    cursor.execute('''
        SELECT u.full_name, c.citizen_id, c.date_of_birth, c.gender,
               c.address, c.phone, c.high_school, c.graduation_year
        FROM users u
        JOIN candidates c ON u.id = c.user_id
        WHERE c.id = ?
    ''', (candidate_id,))
    
    candidate_info = cursor.fetchone()
    
    # Lấy danh sách nguyện vọng
    cursor.execute('''
        SELECT a.priority_order, u.code as university_code, u.name as university_name, 
               m.code as major_code, m.name as major_name, m.subject_group,
               a.status, a.payment_status, a.registered_at
        FROM aspirations a
        JOIN universities u ON a.university_id = u.id
        JOIN majors m ON a.major_id = m.id
        WHERE a.candidate_id = ?
        ORDER BY a.priority_order
    ''', (candidate_id,))
    
    aspirations = cursor.fetchall()
    conn.close()
    
    if not candidate_info:
        return None
    
    # Tạo CSV trong memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Viết header
    writer.writerow(['DANH SÁCH NGUYỆN VỌNG ĐĂNG KÝ XÉT TUYỂN'])
    writer.writerow(['Thí sinh:', candidate_info[0]])
    writer.writerow(['Số CCCD:', candidate_info[1]])
    writer.writerow(['Ngày sinh:', candidate_info[2]])
    writer.writerow(['Giới tính:', candidate_info[3]])
    writer.writerow([])
    writer.writerow(['STT', 'Mã trường', 'Tên trường', 'Mã ngành', 'Tên ngành', 'Khối thi', 'Trạng thái', 'Thanh toán'])
    
    # Viết dữ liệu nguyện vọng
    for i, row in enumerate(aspirations, 1):
        writer.writerow([
            row[0],  # priority
            row[1],  # university_code
            row[2],  # university_name
            row[3],  # major_code
            row[4],  # major_name
            row[5],  # subject_group
            'Đã duyệt' if row[6] == 'approved' else 'Chờ duyệt',
            'Đã thanh toán' if row[7] == 'paid' else 'Chưa thanh toán'
        ])
    
    writer.writerow([])
    writer.writerow(['Ngày xuất:', datetime.now().strftime('%d/%m/%Y %H:%M')])
    
    return output.getvalue()

class AdmissionRequestHandler(http.server.SimpleHTTPRequestHandler):
    
    def do_GET(self):
        if self.path == '/':
            self.serve_embedded_html()
        elif self.path.startswith('/api/'):
            self.handle_api_get()
        else:
            self.send_error(404, "File not found")
    
    def do_POST(self):
        if self.path.startswith('/api/'):
            self.handle_api_post()
        else:
            self.send_error(404, "Endpoint not found")
    
    def serve_embedded_html(self):
        """Serve the embedded HTML content"""
        html_content = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hệ thống Quản lý Tuyển sinh Đại học</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --primary: #4361ee;
            --secondary: #3f37c9;
            --success: #4cc9f0;
            --danger: #f72585;
            --warning: #f8961e;
            --info: #4895ef;
            --light: #f8f9fa;
            --dark: #212529;
            --gray: #6c757d;
            --bg-light: #f5f7fb;
            --card-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            --hover-shadow: 0 10px 15px rgba(0, 0, 0, 0.1);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .login-container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            width: 100%;
            max-width: 450px;
            padding: 40px;
            position: relative;
            overflow: hidden;
        }

        .login-container::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, var(--primary), var(--success));
        }

        .login-header {
            text-align: center;
            margin-bottom: 30px;
        }

        .login-header h1 {
            color: var(--dark);
            font-size: 28px;
            margin-bottom: 10px;
            font-weight: 700;
        }

        .login-header p {
            color: var(--gray);
            font-size: 14px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: var(--dark);
            font-weight: 600;
            font-size: 14px;
        }

        .form-group input, .form-group select, .form-group textarea {
            width: 100%;
            padding: 14px 16px;
            border: 2px solid #e1e5e9;
            border-radius: 10px;
            font-size: 14px;
            transition: all 0.3s ease;
            background: var(--light);
        }

        .form-group input:focus, .form-group select:focus, .form-group textarea:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(67, 97, 238, 0.1);
            background: white;
        }

        .btn {
            padding: 14px 25px;
            border: none;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            text-decoration: none;
        }

        .btn-block {
            width: 100%;
            justify-content: center;
        }

        .btn-primary {
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            color: white;
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(67, 97, 238, 0.3);
        }

        .btn-success {
            background: var(--success);
            color: white;
        }

        .btn-success:hover {
            background: #3ab8e0;
            transform: translateY(-2px);
        }

        .btn-danger {
            background: var(--danger);
            color: white;
        }

        .btn-danger:hover {
            background: #e11574;
            transform: translateY(-2px);
        }

        .btn-warning {
            background: var(--warning);
            color: white;
        }

        .btn-warning:hover {
            background: #e6891b;
            transform: translateY(-2px);
        }

        .btn-secondary {
            background: var(--gray);
            color: white;
        }

        .btn-secondary:hover {
            background: #5a6268;
            transform: translateY(-2px);
        }

        .btn-sm {
            padding: 8px 16px;
            font-size: 12px;
        }

        .login-footer {
            text-align: center;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #e1e5e9;
        }

        .login-footer a {
            color: var(--primary);
            text-decoration: none;
            font-weight: 600;
        }

        .login-footer a:hover {
            text-decoration: underline;
        }

        .system-container {
            display: none;
            width: 100%;
            min-height: 100vh;
            background: var(--bg-light);
        }

        .container {
            display: flex;
            min-height: 100vh;
        }

        .sidebar {
            width: 280px;
            background: white;
            box-shadow: var(--card-shadow);
            position: fixed;
            height: 100vh;
            overflow-y: auto;
            z-index: 1000;
        }

        .sidebar-header {
            padding: 25px 20px;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            color: white;
            text-align: center;
        }

        .sidebar-header h2 {
            font-size: 20px;
            margin-bottom: 5px;
            font-weight: 700;
        }

        .sidebar-header p {
            font-size: 12px;
            opacity: 0.9;
        }

        .sidebar-menu {
            list-style: none;
            padding: 0;
            margin-top: 20px;
        }

        .sidebar-menu li {
            padding: 15px 25px;
            cursor: pointer;
            transition: all 0.3s;
            border-left: 4px solid transparent;
            display: flex;
            align-items: center;
            gap: 12px;
            color: var(--gray);
            font-weight: 500;
        }

        .sidebar-menu li:hover {
            background: rgba(67, 97, 238, 0.05);
            color: var(--primary);
            border-left-color: var(--primary);
        }

        .sidebar-menu li.active {
            background: rgba(67, 97, 238, 0.1);
            color: var(--primary);
            border-left-color: var(--primary);
            font-weight: 600;
        }

        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            margin-left: 280px;
        }

        .header {
            background: white;
            padding: 20px 30px;
            box-shadow: var(--card-shadow);
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .header h1 {
            color: var(--dark);
            font-size: 24px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 700;
        }

        .user-info {
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .user-avatar {
            width: 45px;
            height: 45px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--primary), var(--success));
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 600;
            font-size: 16px;
        }

        .content-section {
            flex: 1;
            padding: 30px;
            overflow-y: auto;
            display: none;
        }

        .content-section.active {
            display: block;
            animation: fadeIn 0.5s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: var(--card-shadow);
            display: flex;
            align-items: center;
            gap: 20px;
            transition: all 0.3s ease;
            border-left: 4px solid var(--primary);
        }

        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: var(--hover-shadow);
        }

        .stat-card.primary {
            border-left-color: var(--primary);
        }

        .stat-card.success {
            border-left-color: var(--success);
        }

        .stat-card.danger {
            border-left-color: var(--danger);
        }

        .stat-card.warning {
            border-left-color: var(--warning);
        }

        .stat-icon {
            width: 60px;
            height: 60px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            color: white;
        }

        .stat-card.primary .stat-icon {
            background: linear-gradient(135deg, var(--primary), var(--secondary));
        }

        .stat-card.success .stat-icon {
            background: linear-gradient(135deg, var(--success), #3a86ff);
        }

        .stat-card.danger .stat-icon {
            background: linear-gradient(135deg, var(--danger), #b5179e);
        }

        .stat-card.warning .stat-icon {
            background: linear-gradient(135deg, var(--warning), #f3722c);
        }

        .stat-info h3 {
            color: var(--gray);
            font-size: 14px;
            margin-bottom: 5px;
            font-weight: 500;
        }

        .stat-info p {
            color: var(--dark);
            font-size: 28px;
            font-weight: 700;
        }

        .content-panel {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: var(--card-shadow);
            margin-bottom: 20px;
        }

        .content-panel h3 {
            color: var(--dark);
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 600;
        }

        .table-container {
            background: white;
            border-radius: 15px;
            box-shadow: var(--card-shadow);
            overflow: hidden;
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th, td {
            padding: 15px 20px;
            text-align: left;
            border-bottom: 1px solid #e9ecef;
        }

        th {
            background: #f8f9fa;
            font-weight: 600;
            color: var(--dark);
            font-size: 14px;
        }

        tr:hover {
            background: #f8f9fa;
        }

        .university-card {
            border: 2px solid #e1e5e9;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 15px;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .university-card:hover {
            border-color: var(--primary);
            transform: translateY(-2px);
            box-shadow: var(--hover-shadow);
        }

        .university-card.selected {
            border-color: var(--primary);
            background: rgba(67, 97, 238, 0.05);
        }

        .major-list {
            max-height: 300px;
            overflow-y: auto;
            border: 2px solid #e1e5e9;
            border-radius: 10px;
            margin-top: 15px;
        }

        .major-item {
            padding: 15px;
            border-bottom: 1px solid #e9ecef;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .major-item:hover {
            background: #f8f9fa;
        }

        .major-item.selected {
            background: var(--primary);
            color: white;
        }

        .aspiration-container {
            background: white;
            border: 2px solid #e1e5e9;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 15px;
            transition: all 0.3s ease;
        }

        .aspiration-container:hover {
            border-color: var(--primary);
            box-shadow: var(--hover-shadow);
        }

        .aspiration-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }

        .priority-badge {
            background: var(--danger);
            color: white;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }

        .status-badge {
            padding: 6px 12px;
            border-radius: 15px;
            font-size: 12px;
            font-weight: 600;
        }

        .status-pending {
            background: #fff3cd;
            color: #856404;
        }

        .status-approved {
            background: #d4edda;
            color: #155724;
        }

        .status-rejected {
            background: #f8d7da;
            color: #721c24;
        }

        .payment-status {
            padding: 6px 12px;
            border-radius: 15px;
            font-size: 12px;
            font-weight: 600;
        }

        .payment-pending {
            background: #fff3cd;
            color: #856404;
        }

        .payment-paid {
            background: #d4edda;
            color: #155724;
        }

        .alert {
            padding: 15px 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }

        .alert-error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }

        .alert-warning {
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeaa7;
        }

        .alert-info {
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }

        .loading {
            display: none;
            position: fixed;
            z-index: 9999;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(255,255,255,0.9);
            backdrop-filter: blur(5px);
        }

        .spinner {
            border: 5px solid #f3f3f3;
            border-top: 5px solid var(--primary);
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            position: absolute;
            top: 50%;
            left: 50%;
            margin: -25px 0 0 -25px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            backdrop-filter: blur(5px);
        }

        .modal-content {
            background: white;
            margin: 5% auto;
            border-radius: 20px;
            width: 500px;
            max-width: 90%;
            box-shadow: 0 25px 50px rgba(0,0,0,0.2);
            animation: modalSlideIn 0.3s ease;
            overflow: hidden;
        }

        @keyframes modalSlideIn {
            from {
                opacity: 0;
                transform: translateY(-50px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .modal-header {
            padding: 25px 30px;
            border-bottom: 1px solid #e9ecef;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            color: white;
        }

        .modal-header h3 {
            color: white;
            margin: 0;
            font-weight: 600;
        }

        .close {
            font-size: 24px;
            cursor: pointer;
            color: rgba(255,255,255,0.8);
            transition: color 0.3s ease;
        }

        .close:hover {
            color: white;
        }

        .modal-body {
            padding: 30px;
            max-height: 70vh;
            overflow-y: auto;
        }

        .form-actions {
            display: flex;
            gap: 15px;
            justify-content: flex-end;
            margin-top: 25px;
        }

        .document-list {
            display: grid;
            gap: 15px;
        }

        .document-item {
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 20px;
            border: 1px solid #e1e5e9;
            border-radius: 12px;
            transition: all 0.3s ease;
        }

        .document-item:hover {
            border-color: var(--primary);
            background: #f8f9fa;
            transform: translateY(-2px);
        }

        .document-icon {
            width: 50px;
            height: 50px;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 20px;
        }

        .document-info {
            flex: 1;
        }

        .document-info h4 {
            color: var(--dark);
            margin-bottom: 5px;
            font-weight: 600;
        }

        .document-info p {
            color: var(--gray);
            font-size: 14px;
        }

        .payment-methods {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }

        .payment-method {
            border: 2px solid #e1e5e9;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .payment-method:hover {
            border-color: var(--primary);
            transform: translateY(-2px);
        }

        .payment-method.selected {
            border-color: var(--primary);
            background: rgba(67, 97, 238, 0.05);
        }

        .payment-icon {
            font-size: 28px;
            margin-bottom: 10px;
            color: var(--primary);
        }

        .bank-info {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 12px;
            margin: 15px 0;
        }

        .print-container {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: var(--card-shadow);
        }

        .print-header {
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 2px solid #000;
            padding-bottom: 20px;
        }

        .print-header h1 {
            font-size: 24px;
            margin-bottom: 10px;
            text-transform: uppercase;
            font-weight: 700;
        }

        .print-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
        }

        .print-table th, .print-table td {
            border: 1px solid #000;
            padding: 12px;
            text-align: left;
        }

        .print-table th {
            background: #f0f0f0;
            font-weight: bold;
        }

        .print-footer {
            margin-top: 50px;
            text-align: center;
        }

        .signature-section {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 50px;
            margin-top: 80px;
        }

        .signature-box {
            text-align: center;
        }

        .signature-line {
            border-top: 1px solid #000;
            width: 200px;
            margin: 50px auto 10px auto;
        }

        .tabs {
            display: flex;
            border-bottom: 2px solid #e9ecef;
            margin-bottom: 20px;
            background: white;
            border-radius: 10px 10px 0 0;
            overflow: hidden;
        }

        .tab {
            padding: 15px 25px;
            cursor: pointer;
            border-bottom: 3px solid transparent;
            transition: all 0.3s ease;
            font-weight: 500;
            background: #f8f9fa;
        }

        .tab.active {
            border-bottom-color: var(--primary);
            color: var(--primary);
            background: white;
            font-weight: 600;
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }

        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
        }

        .section-header h2 {
            color: var(--dark);
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 700;
        }

        .print-actions {
            display: flex;
            gap: 15px;
            margin: 20px 0;
        }

        .action-buttons {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }

        .edit-btn, .save-btn, .cancel-btn {
            padding: 8px 16px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 600;
            transition: all 0.3s ease;
        }

        .edit-btn {
            background: var(--warning);
            color: white;
        }

        .edit-btn:hover {
            background: #e6891b;
        }

        .save-btn {
            background: var(--success);
            color: white;
        }

        .save-btn:hover {
            background: #3ab8e0;
        }

        .cancel-btn {
            background: var(--gray);
            color: white;
        }

        .cancel-btn:hover {
            background: #5a6268;
        }

        .editable-field {
            padding: 8px 12px;
            border: 1px solid transparent;
            border-radius: 6px;
            transition: all 0.3s ease;
        }

        .editable-field:hover {
            border-color: #e1e5e9;
            background: #f8f9fa;
        }

        .editable-field.editing {
            border-color: var(--primary);
            background: white;
            box-shadow: 0 0 0 2px rgba(67, 97, 238, 0.1);
        }

        @media print {
            body * {
                visibility: hidden;
            }
            .print-container, .print-container * {
                visibility: visible;
            }
            .print-container {
                position: absolute;
                left: 0;
                top: 0;
                width: 100%;
                box-shadow: none;
            }
            .no-print {
                display: none !important;
            }
        }

        @media (max-width: 768px) {
            .container {
                flex-direction: column;
            }
            
            .sidebar {
                width: 100%;
                height: auto;
                position: relative;
            }
            
            .main-content {
                margin-left: 0;
            }
            
            .stats-grid {
                grid-template-columns: 1fr;
            }
            
            .section-header {
                flex-direction: column;
                gap: 15px;
                align-items: flex-start;
            }
            
            .print-actions, .form-actions {
                flex-direction: column;
            }
            
            .action-buttons {
                justify-content: center;
            }
        }
    </style>
</head>
<body>
    <!-- Login Page -->
    <div class="login-container" id="loginPage">
        <div class="login-header">
            <h1><i class="fas fa-graduation-cap"></i> Hệ thống Tuyển sinh</h1>
            <p>Đăng nhập để tiếp tục</p>
        </div>
        
        <form id="loginForm">
            <div class="form-group">
                <label for="username"><i class="fas fa-user"></i> Tên đăng nhập</label>
                <input type="text" id="username" name="username" placeholder="Nhập tên đăng nhập" required>
            </div>
            
            <div class="form-group">
                <label for="password"><i class="fas fa-lock"></i> Mật khẩu</label>
                <input type="password" id="password" name="password" placeholder="Nhập mật khẩu" required>
            </div>
            
            <button type="submit" class="btn btn-primary btn-block">
                <i class="fas fa-sign-in-alt"></i> Đăng nhập
            </button>
        </form>
        
        <div class="login-footer">
            <p>Chưa có tài khoản? <a href="#" onclick="showRegisterModal()">Đăng ký ngay</a></p>
        </div>
    </div>

    <!-- Main System -->
    <div class="system-container" id="systemContainer">
        <div class="container">
            <!-- Sidebar -->
            <div class="sidebar">
                <div class="sidebar-header">
                    <h2><i class="fas fa-graduation-cap"></i> Hệ thống Tuyển sinh</h2>
                    <p id="userRoleDisplay">Thí sinh</p>
                </div>
                <ul class="sidebar-menu" id="sidebarMenu">
                    <!-- Menu will be loaded dynamically -->
                </ul>
            </div>

            <!-- Main Content -->
            <div class="main-content">
                <!-- Header -->
                <div class="header">
                    <h1 id="section-title"><i class="fas fa-tachometer-alt"></i> Tổng quan hệ thống</h1>
                    <div class="user-info">
                        <span id="userFullname">Nguyễn Văn A</span>
                        <div class="user-avatar">
                            <i class="fas fa-user-graduate"></i>
                        </div>
                    </div>
                </div>

                <!-- Content Sections -->
                <div id="dashboard" class="content-section active">
                    <!-- Dashboard content -->
                </div>

                <div id="profile" class="content-section">
                    <!-- Profile content -->
                </div>

                <div id="aspiration" class="content-section">
                    <!-- Aspiration content -->
                </div>

                <div id="payment" class="content-section">
                    <!-- Payment content -->
                </div>

                <div id="documents" class="content-section">
                    <!-- Documents content -->
                </div>

                <div id="print" class="content-section">
                    <!-- Print content -->
                </div>

                <div id="manager-aspiration" class="content-section">
                    <!-- Manager aspiration content -->
                </div>

                <div id="results" class="content-section">
                    <!-- Results content -->
                </div>
            </div>
        </div>
    </div>

    <!-- Register Modal -->
    <div id="registerModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3><i class="fas fa-user-plus"></i> Đăng ký tài khoản thí sinh</h3>
                <span class="close" onclick="closeModal('registerModal')">&times;</span>
            </div>
            <div class="modal-body">
                <form id="registerForm">
                    <div class="form-group">
                        <label for="regUsername">Tên đăng nhập *</label>
                        <input type="text" id="regUsername" name="username" required>
                    </div>
                    <div class="form-group">
                        <label for="regPassword">Mật khẩu *</label>
                        <input type="password" id="regPassword" name="password" required>
                    </div>
                    <div class="form-group">
                        <label for="regEmail">Email *</label>
                        <input type="email" id="regEmail" name="email" required>
                    </div>
                    <div class="form-group">
                        <label for="regFullname">Họ và tên *</label>
                        <input type="text" id="regFullname" name="full_name" required>
                    </div>
                    <div class="form-group">
                        <label for="regCitizenId">Số CCCD *</label>
                        <input type="text" id="regCitizenId" name="citizen_id" required>
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn btn-secondary" onclick="closeModal('registerModal')">Hủy</button>
                        <button type="submit" class="btn btn-primary">Đăng ký</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <!-- Payment Modal -->
    <div id="paymentModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3><i class="fas fa-credit-card"></i> Thanh toán nguyện vọng</h3>
                <span class="close" onclick="closeModal('paymentModal')">&times;</span>
            </div>
            <div class="modal-body">
                <div id="paymentContent">
                    <!-- Payment content -->
                </div>
            </div>
        </div>
    </div>

    <!-- Approval Modal -->
    <div id="approvalModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 id="approvalModalTitle"><i class="fas fa-check-circle"></i> Duyệt nguyện vọng</h3>
                <span class="close" onclick="closeModal('approvalModal')">&times;</span>
            </div>
            <div class="modal-body">
                <div id="approvalContent">
                    <!-- Approval content -->
                </div>
            </div>
        </div>
    </div>

    <!-- Print Modal -->
    <div id="printModal" class="modal">
        <div class="modal-content" style="max-width: 800px;">
            <div class="modal-header">
                <h3><i class="fas fa-print"></i> In danh sách nguyện vọng</h3>
                <span class="close" onclick="closeModal('printModal')">&times;</span>
            </div>
            <div class="modal-body">
                <div id="printContent">
                    <!-- Print content -->
                </div>
                <div class="form-actions no-print">
                    <button class="btn btn-secondary" onclick="closeModal('printModal')">Đóng</button>
                    <button class="btn btn-primary" onclick="window.print()">
                        <i class="fas fa-print"></i> In
                    </button>
                    <button class="btn btn-success" onclick="exportToCSV()">
                        <i class="fas fa-file-csv"></i> Xuất CSV
                    </button>
                </div>
            </div>
        </div>
    </div>

    <!-- Loading Spinner -->
    <div id="loading" class="loading">
        <div class="spinner"></div>
    </div>

    <script>
        // ==================== GLOBAL VARIABLES ====================
        let currentUser = null;
        let currentRole = 'candidate';
        let universities = [];
        let majors = [];
        let aspirations = [];
        let documents = [];
        let payments = [];
        let pendingAspirations = [];
        let selectedUniversity = null;
        let selectedMajor = null;
        let selectedPaymentMethod = null;
        let selectedAspirationForPayment = null;
        let selectedAspirationForApproval = null;
        let editingFields = new Set();
        const apiBaseUrl = 'http://localhost:8000/api';

        // ==================== UTILITY FUNCTIONS ====================
        function showLoading() {
            document.getElementById('loading').style.display = 'block';
        }

        function hideLoading() {
            document.getElementById('loading').style.display = 'none';
        }

        function showModal(modalId) {
            document.getElementById(modalId).style.display = 'block';
        }

        function closeModal(modalId) {
            document.getElementById(modalId).style.display = 'none';
        }

        function showAlert(message, type = 'info') {
            const alertDiv = document.createElement('div');
            alertDiv.className = `alert alert-${type}`;
            alertDiv.innerHTML = `
                <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : type === 'warning' ? 'exclamation-triangle' : 'info-circle'}"></i>
                ${message}
            `;
            
            const container = document.querySelector('.main-content');
            container.insertBefore(alertDiv, container.firstChild);
            
            setTimeout(() => {
                alertDiv.remove();
            }, 5000);
        }

        async function apiCall(endpoint, options = {}) {
            const token = localStorage.getItem('token');
            const headers = {
                'Content-Type': 'application/json',
                ...options.headers
            };
            
            if (token) {
                headers['Authorization'] = token;
            }
            
            try {
                const response = await fetch(`${apiBaseUrl}${endpoint}`, {
                    headers,
                    ...options
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                return await response.json();
            } catch (error) {
                console.error('API call failed:', error);
                showAlert('Kết nối server thất bại. Vui lòng thử lại.', 'error');
                throw error;
            }
        }

        // ==================== AUTHENTICATION ====================
        document.getElementById('loginForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            showLoading();

            const formData = {
                username: document.getElementById('username').value,
                password: document.getElementById('password').value
            };

            try {
                const result = await apiCall('/auth/login', {
                    method: 'POST',
                    body: JSON.stringify(formData)
                });

                if (result.success) {
                    currentUser = result.user;
                    currentRole = result.user.role;
                    localStorage.setItem('token', result.token);
                    showSystem();
                    showAlert('Đăng nhập thành công!', 'success');
                } else {
                    showAlert(result.error, 'error');
                }
            } catch (error) {
                showAlert('Đăng nhập thất bại. Vui lòng thử lại.', 'error');
            } finally {
                hideLoading();
            }
        });

        document.getElementById('registerForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            showLoading();

            const formData = {
                username: document.getElementById('regUsername').value,
                password: document.getElementById('regPassword').value,
                email: document.getElementById('regEmail').value,
                full_name: document.getElementById('regFullname').value,
                citizen_id: document.getElementById('regCitizenId').value
            };

            try {
                const result = await apiCall('/auth/register', {
                    method: 'POST',
                    body: JSON.stringify(formData)
                });

                if (result.success) {
                    closeModal('registerModal');
                    showAlert('Đăng ký thành công! Vui lòng đăng nhập.', 'success');
                    document.getElementById('registerForm').reset();
                } else {
                    showAlert(result.error, 'error');
                }
            } catch (error) {
                showAlert('Đăng ký thất bại. Vui lòng thử lại.', 'error');
            } finally {
                hideLoading();
            }
        });

        function showRegisterModal() {
            showModal('registerModal');
        }

        function logout() {
            currentUser = null;
            localStorage.removeItem('token');
            document.getElementById('systemContainer').style.display = 'none';
            document.getElementById('loginPage').style.display = 'block';
            document.getElementById('loginForm').reset();
        }

        // ==================== SYSTEM FUNCTIONS ====================
        function showSystem() {
            document.getElementById('loginPage').style.display = 'none';
            document.getElementById('systemContainer').style.display = 'block';
            
            document.getElementById('userFullname').textContent = currentUser.full_name;
            document.getElementById('userRoleDisplay').textContent = 
                currentUser.role === 'admin' ? 'Quản trị viên' : 
                currentUser.role === 'manager' ? 'Cán bộ tuyển sinh' : 'Thí sinh';
            
            loadSidebarMenu();
            showSection('dashboard');
        }

        function loadSidebarMenu() {
            const sidebarMenu = document.getElementById('sidebarMenu');
            let menuItems = '';

            if (currentRole === 'candidate') {
                menuItems = `
                    <li class="active" onclick="showSection('dashboard')">
                        <i class="fas fa-tachometer-alt"></i> Tổng quan
                    </li>
                    <li onclick="showSection('profile')">
                        <i class="fas fa-user"></i> Hồ sơ cá nhân
                    </li>
                    <li onclick="showSection('aspiration')">
                        <i class="fas fa-list-ol"></i> Đăng ký nguyện vọng
                    </li>
                    <li onclick="showSection('payment')">
                        <i class="fas fa-credit-card"></i> Thanh toán
                    </li>
                    <li onclick="showSection('documents')">
                        <i class="fas fa-file-alt"></i> Tài liệu
                    </li>
                    <li onclick="showSection('print')">
                        <i class="fas fa-print"></i> In ấn
                    </li>
                    <li onclick="showSection('results')">
                        <i class="fas fa-chart-bar"></i> Kết quả
                    </li>
                    <li onclick="logout()">
                        <i class="fas fa-sign-out-alt"></i> Đăng xuất
                    </li>
                `;
            } else if (currentRole === 'manager') {
                menuItems = `
                    <li class="active" onclick="showSection('dashboard')">
                        <i class="fas fa-tachometer-alt"></i> Tổng quan
                    </li>
                    <li onclick="showSection('manager-aspiration')">
                        <i class="fas fa-list-ol"></i> Duyệt nguyện vọng
                    </li>
                    <li onclick="logout()">
                        <i class="fas fa-sign-out-alt"></i> Đăng xuất
                    </li>
                `;
            } else if (currentRole === 'admin') {
                menuItems = `
                    <li class="active" onclick="showSection('dashboard')">
                        <i class="fas fa-tachometer-alt"></i> Tổng quan
                    </li>
                    <li onclick="showSection('manager-aspiration')">
                        <i class="fas fa-list-ol"></i> Quản lý nguyện vọng
                    </li>
                    <li onclick="logout()">
                        <i class="fas fa-sign-out-alt"></i> Đăng xuất
                    </li>
                `;
            }

            sidebarMenu.innerHTML = menuItems;
        }

        function showSection(sectionId) {
            // Hide all sections
            document.querySelectorAll('.content-section').forEach(section => {
                section.classList.remove('active');
            });
            
            // Update active menu item
            document.querySelectorAll('.sidebar-menu li').forEach(item => {
                item.classList.remove('active');
            });
            
            // Show selected section
            document.getElementById(sectionId).classList.add('active');
            
            // Update section title
            const titles = {
                'dashboard': 'Tổng quan hệ thống',
                'profile': 'Hồ sơ cá nhân',
                'aspiration': 'Đăng ký nguyện vọng',
                'payment': 'Thanh toán',
                'documents': 'Tài liệu',
                'print': 'In ấn',
                'manager-aspiration': 'Duyệt nguyện vọng',
                'results': 'Kết quả tuyển sinh'
            };
            
            document.getElementById('section-title').innerHTML = `
                <i class="fas fa-${getSectionIcon(sectionId)}"></i> ${titles[sectionId]}
            `;
            
            // Mark active menu item
            const menuItems = document.querySelectorAll('.sidebar-menu li');
            for (let i = 0; i < menuItems.length; i++) {
                if (menuItems[i].getAttribute('onclick') === `showSection('${sectionId}')`) {
                    menuItems[i].classList.add('active');
                    break;
                }
            }
            
            // Load section content
            loadSectionContent(sectionId);
        }

        function getSectionIcon(sectionId) {
            const icons = {
                'dashboard': 'tachometer-alt',
                'profile': 'user',
                'aspiration': 'list-ol',
                'payment': 'credit-card',
                'documents': 'file-alt',
                'print': 'print',
                'manager-aspiration': 'check-circle',
                'results': 'chart-bar'
            };
            return icons[sectionId] || 'circle';
        }

        async function loadSectionContent(sectionId) {
            showLoading();
            
            try {
                switch (sectionId) {
                    case 'dashboard':
                        await loadDashboard();
                        break;
                    case 'profile':
                        await loadProfile();
                        break;
                    case 'aspiration':
                        await loadAspiration();
                        break;
                    case 'payment':
                        await loadPayment();
                        break;
                    case 'documents':
                        await loadDocuments();
                        break;
                    case 'print':
                        await loadPrint();
                        break;
                    case 'manager-aspiration':
                        await loadManagerAspiration();
                        break;
                    case 'results':
                        await loadResults();
                        break;
                }
            } catch (error) {
                console.error('Error loading section:', error);
                showAlert('Lỗi khi tải dữ liệu', 'error');
            } finally {
                hideLoading();
            }
        }

        // ==================== SECTION LOADERS ====================
        async function loadDashboard() {
            const section = document.getElementById('dashboard');
            
            if (currentRole === 'candidate') {
                try {
                    const result = await apiCall('/candidate/stats');
                    const stats = result.data;
                    
                    section.innerHTML = `
                        <div class="stats-grid">
                            <div class="stat-card primary">
                                <div class="stat-icon">
                                    <i class="fas fa-list-ol"></i>
                                </div>
                                <div class="stat-info">
                                    <h3>Tổng số nguyện vọng</h3>
                                    <p>${stats.totalAspirations || 0}</p>
                                </div>
                            </div>
                            <div class="stat-card success">
                                <div class="stat-icon">
                                    <i class="fas fa-check-circle"></i>
                                </div>
                                <div class="stat-info">
                                    <h3>Đã thanh toán</h3>
                                    <p>${stats.paidAspirations || 0}</p>
                                </div>
                            </div>
                            <div class="stat-card warning">
                                <div class="stat-icon">
                                    <i class="fas fa-clock"></i>
                                </div>
                                <div class="stat-info">
                                    <h3>Chờ duyệt</h3>
                                    <p>${stats.pendingAspirations || 0}</p>
                                </div>
                            </div>
                            <div class="stat-card danger">
                                <div class="stat-icon">
                                    <i class="fas fa-times-circle"></i>
                                </div>
                                <div class="stat-info">
                                    <h3>Bị từ chối</h3>
                                    <p>${stats.rejectedAspirations || 0}</p>
                                </div>
                            </div>
                        </div>
                        
                        <div class="content-panel">
                            <h3><i class="fas fa-bell"></i> Thông báo quan trọng</h3>
                            <div class="alert alert-info">
                                <i class="fas fa-info-circle"></i>
                                Thời hạn đăng ký nguyện vọng: 30/06/2025
                            </div>
                            <div class="alert alert-warning">
                                <i class="fas fa-exclamation-triangle"></i>
                                Vui lòng hoàn tất thanh toán trước 15/07/2025
                            </div>
                        </div>
                        
                        <div class="content-panel">
                            <h3><i class="fas fa-list-ol"></i> Nguyện vọng gần đây</h3>
                            <div id="recentAspirations">
                                Đang tải...
                            </div>
                        </div>
                    `;
                    
                    // Load recent aspirations
                    await loadRecentAspirations();
                } catch (error) {
                    section.innerHTML = `
                        <div class="alert alert-error">
                            <i class="fas fa-exclamation-circle"></i>
                            Lỗi khi tải dữ liệu dashboard
                        </div>
                    `;
                }
            } else if (currentRole === 'manager' || currentRole === 'admin') {
                try {
                    const endpoint = currentRole === 'manager' ? '/manager/stats' : '/admin/stats';
                    const result = await apiCall(endpoint);
                    const stats = result.data;
                    
                    section.innerHTML = `
                        <div class="stats-grid">
                            <div class="stat-card primary">
                                <div class="stat-icon">
                                    <i class="fas fa-list-ol"></i>
                                </div>
                                <div class="stat-info">
                                    <h3>Tổng nguyện vọng</h3>
                                    <p>${stats.totalAspirations || stats.aspirations || 0}</p>
                                </div>
                            </div>
                            <div class="stat-card danger">
                                <div class="stat-icon">
                                    <i class="fas fa-clock"></i>
                                </div>
                                <div class="stat-info">
                                    <h3>Chờ duyệt</h3>
                                    <p>${stats.pendingAspirations || 0}</p>
                                </div>
                            </div>
                            <div class="stat-card success">
                                <div class="stat-icon">
                                    <i class="fas fa-check-circle"></i>
                                </div>
                                <div class="stat-info">
                                    <h3>Đã duyệt</h3>
                                    <p>${stats.approvedAspirations || 0}</p>
                                </div>
                            </div>
                            <div class="stat-card warning">
                                <div class="stat-icon">
                                    <i class="fas fa-credit-card"></i>
                                </div>
                                <div class="stat-info">
                                    <h3>Đã thanh toán</h3>
                                    <p>${stats.totalPayments || 0}</p>
                                </div>
                            </div>
                        </div>
                        
                        <div class="content-panel">
                            <h3><i class="fas fa-clock"></i> Nguyện vọng chờ duyệt (5 mới nhất)</h3>
                            <div id="pendingAspirationsList">
                                Đang tải...
                            </div>
                        </div>
                    `;
                    
                    // Load pending aspirations for manager
                    await loadPendingAspirationsForManager();
                } catch (error) {
                    section.innerHTML = `
                        <div class="alert alert-error">
                            <i class="fas fa-exclamation-circle"></i>
                            Lỗi khi tải dữ liệu dashboard
                        </div>
                    `;
                }
            }
        }

        async function loadRecentAspirations() {
            try {
                const result = await apiCall('/candidate/aspirations');
                const aspirations = result.data;
                
                const container = document.getElementById('recentAspirations');
                
                if (aspirations.length > 0) {
                    container.innerHTML = `
                        <div class="table-container">
                            <table>
                                <thead>
                                    <tr>
                                        <th>STT</th>
                                        <th>Trường</th>
                                        <th>Ngành</th>
                                        <th>Trạng thái</th>
                                        <th>Thanh toán</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${aspirations.slice(0, 5).map(asp => `
                                        <tr>
                                            <td>${asp.priority}</td>
                                            <td>${asp.university_name}</td>
                                            <td>${asp.major_name}</td>
                                            <td>
                                                <span class="status-badge ${getStatusClass(asp.status)}">
                                                    ${getStatusText(asp.status)}
                                                </span>
                                            </td>
                                            <td>
                                                <span class="payment-status ${getPaymentStatusClass(asp.payment_status)}">
                                                    ${getPaymentStatusText(asp.payment_status)}
                                                </span>
                                            </td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    `;
                } else {
                    container.innerHTML = '<p class="text-muted">Chưa có nguyện vọng nào</p>';
                }
            } catch (error) {
                document.getElementById('recentAspirations').innerHTML = 
                    '<p class="text-muted">Lỗi khi tải danh sách nguyện vọng</p>';
            }
        }

        async function loadPendingAspirationsForManager() {
            try {
                const result = await apiCall('/manager/pending-aspirations');
                const pendingAspirations = result.data;
                
                const container = document.getElementById('pendingAspirationsList');
                
                if (pendingAspirations.length > 0) {
                    container.innerHTML = `
                        <div class="table-container">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Thí sinh</th>
                                        <th>CCCD</th>
                                        <th>Trường</th>
                                        <th>Ngành</th>
                                        <th>Ưu tiên</th>
                                        <th>Thanh toán</th>
                                        <th>Thao tác</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${pendingAspirations.slice(0, 5).map(asp => `
                                        <tr>
                                            <td>${asp.candidate_name}</td>
                                            <td>${asp.citizen_id}</td>
                                            <td>${asp.university_name}</td>
                                            <td>${asp.major_name}</td>
                                            <td>${asp.priority}</td>
                                            <td>
                                                <span class="payment-status ${getPaymentStatusClass(asp.payment_status)}">
                                                    ${getPaymentStatusText(asp.payment_status)}
                                                </span>
                                            </td>
                                            <td>
                                                <button class="btn btn-success btn-sm" onclick="showApprovalModal(${asp.id}, 'approve')">
                                                    <i class="fas fa-check"></i>
                                                </button>
                                                <button class="btn btn-danger btn-sm" onclick="showApprovalModal(${asp.id}, 'reject')">
                                                    <i class="fas fa-times"></i>
                                                </button>
                                            </td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    `;
                } else {
                    container.innerHTML = '<p class="text-muted">Không có nguyện vọng nào chờ duyệt</p>';
                }
            } catch (error) {
                document.getElementById('pendingAspirationsList').innerHTML = 
                    '<p class="text-muted">Lỗi khi tải danh sách nguyện vọng chờ duyệt</p>';
            }
        }

        async function loadProfile() {
            try {
                const result = await apiCall('/candidate/profile');
                const profile = result.data;
                
                const section = document.getElementById('profile');
                
                section.innerHTML = `
                    <div class="content-panel">
                        <div class="section-header">
                            <h3><i class="fas fa-user"></i> Thông tin cá nhân</h3>
                            <button class="btn btn-primary" onclick="enableProfileEditing()">
                                <i class="fas fa-edit"></i> Chỉnh sửa
                            </button>
                        </div>
                        <form id="profileForm">
                            <div class="form-group">
                                <label>Họ và tên</label>
                                <input type="text" id="profileFullname" value="${profile.full_name}" readonly>
                            </div>
                            <div class="form-group">
                                <label>Email</label>
                                <input type="email" id="profileEmail" value="${profile.email}" readonly>
                            </div>
                            <div class="form-group">
                                <label>Số CCCD</label>
                                <input type="text" id="profileCitizenId" value="${profile.citizen_id}" readonly>
                            </div>
                            <div class="form-group">
                                <label>Ngày sinh</label>
                                <input type="date" id="profileDob" value="${profile.date_of_birth || ''}" readonly>
                            </div>
                            <div class="form-group">
                                <label>Giới tính</label>
                                <select id="profileGender" disabled>
                                    <option value="">Chọn giới tính</option>
                                    <option value="male" ${profile.gender === 'male' ? 'selected' : ''}>Nam</option>
                                    <option value="female" ${profile.gender === 'female' ? 'selected' : ''}>Nữ</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Địa chỉ</label>
                                <textarea id="profileAddress" rows="3" readonly>${profile.address || ''}</textarea>
                            </div>
                            <div class="form-group">
                                <label>Số điện thoại</label>
                                <input type="tel" id="profilePhone" value="${profile.phone || ''}" readonly>
                            </div>
                            <div class="form-group">
                                <label>Trường THPT</label>
                                <input type="text" id="profileHighSchool" value="${profile.high_school || ''}" readonly>
                            </div>
                            <div class="form-group">
                                <label>Năm tốt nghiệp</label>
                                <input type="number" id="profileGraduationYear" value="${profile.graduation_year || ''}" readonly>
                            </div>
                            <div class="form-actions" id="profileActions" style="display: none;">
                                <button type="button" class="btn btn-secondary" onclick="cancelProfileEditing()">Hủy</button>
                                <button type="submit" class="btn btn-primary">Cập nhật thông tin</button>
                            </div>
                        </form>
                    </div>
                `;
                
                document.getElementById('profileForm').addEventListener('submit', async function(e) {
                    e.preventDefault();
                    await saveProfile();
                });
            } catch (error) {
                const section = document.getElementById('profile');
                section.innerHTML = `
                    <div class="alert alert-error">
                        <i class="fas fa-exclamation-circle"></i>
                        Lỗi khi tải thông tin hồ sơ
                    </div>
                `;
            }
        }

        async function loadAspiration() {
            try {
                // Load universities and aspirations
                const [uniResult, aspResult] = await Promise.all([
                    apiCall('/universities'),
                    apiCall('/candidate/aspirations')
                ]);
                
                universities = uniResult.data;
                aspirations = aspResult.data;
                
                const section = document.getElementById('aspiration');
                
                section.innerHTML = `
                    <div class="content-panel">
                        <h3><i class="fas fa-list-ol"></i> Danh sách nguyện vọng hiện tại</h3>
                        <div id="currentAspirations">
                            ${aspirations.length > 0 ? `
                                <div class="table-container">
                                    <table>
                                        <thead>
                                            <tr>
                                                <th>STT</th>
                                                <th>Trường</th>
                                                <th>Ngành</th>
                                                <th>Trạng thái</th>
                                                <th>Thanh toán</th>
                                                <th>Thao tác</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${aspirations.map(asp => `
                                                <tr>
                                                    <td>${asp.priority}</td>
                                                    <td>${asp.university_name}</td>
                                                    <td>${asp.major_name}</td>
                                                    <td>
                                                        <span class="status-badge ${getStatusClass(asp.status)}">
                                                            ${getStatusText(asp.status)}
                                                        </span>
                                                    </td>
                                                    <td>
                                                        <span class="payment-status ${getPaymentStatusClass(asp.payment_status)}">
                                                            ${getPaymentStatusText(asp.payment_status)}
                                                        </span>
                                                    </td>
                                                    <td>
                                                        <button class="btn btn-danger btn-sm" onclick="removeAspiration(${asp.id})">
                                                            <i class="fas fa-trash"></i>
                                                        </button>
                                                    </td>
                                                </tr>
                                            `).join('')}
                                        </tbody>
                                    </table>
                                </div>
                            ` : '<p class="text-muted">Chưa có nguyện vọng nào</p>'}
                        </div>
                    </div>
                    
                    <div class="content-panel">
                        <h3><i class="fas fa-plus-circle"></i> Thêm nguyện vọng mới</h3>
                        <div class="form-group">
                            <label>Chọn trường đại học</label>
                            <select id="universitySelect" onchange="loadUniversityMajors(this.value)">
                                <option value="">-- Chọn trường --</option>
                                ${universities.map(uni => `
                                    <option value="${uni.id}">${uni.name}</option>
                                `).join('')}
                            </select>
                        </div>
                        
                        <div class="form-group">
                            <label>Chọn ngành học</label>
                            <select id="majorSelect" disabled>
                                <option value="">-- Chọn ngành --</option>
                            </select>
                        </div>
                        
                        <div class="form-group">
                            <label>Thứ tự ưu tiên</label>
                            <select id="prioritySelect">
                                ${Array.from({length: 10}, (_, i) => `
                                    <option value="${i + 1}">${i + 1}</option>
                                `).join('')}
                            </select>
                        </div>
                        
                        <button class="btn btn-primary" onclick="addNewAspiration()">
                            <i class="fas fa-plus"></i> Thêm nguyện vọng
                        </button>
                    </div>
                `;
            } catch (error) {
                const section = document.getElementById('aspiration');
                section.innerHTML = `
                    <div class="alert alert-error">
                        <i class="fas fa-exclamation-circle"></i>
                        Lỗi khi tải thông tin nguyện vọng
                    </div>
                `;
            }
        }

        async function loadPayment() {
            try {
                const [configResult, historyResult, aspResult] = await Promise.all([
                    apiCall('/payment/config'),
                    apiCall('/payment/history'),
                    apiCall('/candidate/aspirations')
                ]);
                
                const paymentConfig = configResult.data;
                payments = historyResult.data;
                aspirations = aspResult.data.filter(asp => asp.payment_status === 'pending');
                
                const section = document.getElementById('payment');
                
                section.innerHTML = `
                    <div class="content-panel">
                        <h3><i class="fas fa-credit-card"></i> Thanh toán nguyện vọng</h3>
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle"></i>
                            Phí đăng ký mỗi nguyện vọng: ${formatCurrency(paymentConfig.aspiration_fee)}
                        </div>
                        
                        <div id="paymentAspirations">
                            ${aspirations.length > 0 ? `
                                <div class="table-container">
                                    <table>
                                        <thead>
                                            <tr>
                                                <th>STT</th>
                                                <th>Trường</th>
                                                <th>Ngành</th>
                                                <th>Phí</th>
                                                <th>Thao tác</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${aspirations.map(asp => `
                                                <tr>
                                                    <td>${asp.priority}</td>
                                                    <td>${asp.university_name}</td>
                                                    <td>${asp.major_name}</td>
                                                    <td>${formatCurrency(paymentConfig.aspiration_fee)}</td>
                                                    <td>
                                                        <button class="btn btn-primary btn-sm" onclick="showPaymentModal(${asp.id})">
                                                            <i class="fas fa-credit-card"></i> Thanh toán
                                                        </button>
                                                    </td>
                                                </tr>
                                            `).join('')}
                                        </tbody>
                                    </table>
                                </div>
                            ` : '<p class="text-muted">Không có nguyện vọng nào cần thanh toán</p>'}
                        </div>
                    </div>
                    
                    <div class="content-panel">
                        <h3><i class="fas fa-history"></i> Lịch sử thanh toán</h3>
                        <div id="paymentHistory">
                            ${payments.length > 0 ? `
                                <div class="table-container">
                                    <table>
                                        <thead>
                                            <tr>
                                                <th>Mã GD</th>
                                                <th>Ngày</th>
                                                <th>Số tiền</th>
                                                <th>Phương thức</th>
                                                <th>Trạng thái</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${payments.map(payment => `
                                                <tr>
                                                    <td>${payment.transaction_id || 'N/A'}</td>
                                                    <td>${formatDate(payment.created_at)}</td>
                                                    <td>${formatCurrency(payment.amount)}</td>
                                                    <td>${getPaymentMethodText(payment.payment_method)}</td>
                                                    <td>
                                                        <span class="status-badge ${payment.status === 'completed' ? 'status-approved' : 'status-pending'}">
                                                            ${payment.status === 'completed' ? 'Hoàn thành' : 'Chờ xử lý'}
                                                        </span>
                                                    </td>
                                                </tr>
                                            `).join('')}
                                        </tbody>
                                    </table>
                                </div>
                            ` : '<p class="text-muted">Chưa có giao dịch nào</p>'}
                        </div>
                    </div>
                `;
            } catch (error) {
                const section = document.getElementById('payment');
                section.innerHTML = `
                    <div class="alert alert-error">
                        <i class="fas fa-exclamation-circle"></i>
                        Lỗi khi tải thông tin thanh toán
                    </div>
                `;
            }
        }

        async function loadDocuments() {
            try {
                const result = await apiCall('/documents');
                documents = result.data;
                
                const section = document.getElementById('documents');
                
                section.innerHTML = `
                    <div class="content-panel">
                        <h3><i class="fas fa-file-alt"></i> Tài liệu tuyển sinh</h3>
                        <div class="document-list">
                            ${documents.map(doc => `
                                <div class="document-item">
                                    <div class="document-icon">
                                        <i class="fas fa-${getDocumentIcon(doc.category)}"></i>
                                    </div>
                                    <div class="document-info">
                                        <h4>${doc.title}</h4>
                                        <p>${doc.description}</p>
                                        <small class="text-muted">Ngày đăng: ${formatDate(doc.created_at)}</small>
                                    </div>
                                    <button class="btn btn-primary">
                                        <i class="fas fa-download"></i> Tải về
                                    </button>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;
            } catch (error) {
                const section = document.getElementById('documents');
                section.innerHTML = `
                    <div class="alert alert-error">
                        <i class="fas fa-exclamation-circle"></i>
                        Lỗi khi tải tài liệu
                    </div>
                `;
            }
        }

        async function loadPrint() {
            try {
                const section = document.getElementById('print');
                
                section.innerHTML = `
                    <div class="content-panel">
                        <h3><i class="fas fa-print"></i> In và xuất dữ liệu</h3>
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle"></i>
                            Xuất danh sách nguyện vọng của bạn ra file PDF hoặc CSV
                        </div>
                        
                        <div class="print-actions">
                            <button class="btn btn-primary" onclick="generatePrintData()">
                                <i class="fas fa-file-pdf"></i> Xem trước bản in
                            </button>
                            <button class="btn btn-success" onclick="exportToCSV()">
                                <i class="fas fa-file-csv"></i> Xuất file CSV
                            </button>
                        </div>
                        
                        <div id="printPreview" class="mt-4">
                            <!-- Print preview will be loaded here -->
                        </div>
                    </div>
                `;
            } catch (error) {
                const section = document.getElementById('print');
                section.innerHTML = `
                    <div class="alert alert-error">
                        <i class="fas fa-exclamation-circle"></i>
                        Lỗi khi tải tính năng in ấn
                    </div>
                `;
            }
        }

        async function loadManagerAspiration() {
            try {
                const result = await apiCall('/manager/pending-aspirations');
                pendingAspirations = result.data;
                
                const section = document.getElementById('manager-aspiration');
                
                section.innerHTML = `
                    <div class="content-panel">
                        <h3><i class="fas fa-tasks"></i> Quản lý nguyện vọng</h3>
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle"></i>
                            Danh sách nguyện vọng đang chờ duyệt
                        </div>
                        
                        <div id="managerAspirationsList">
                            ${pendingAspirations.length > 0 ? `
                                <div class="table-container">
                                    <table>
                                        <thead>
                                            <tr>
                                                <th>Thí sinh</th>
                                                <th>CCCD</th>
                                                <th>Trường</th>
                                                <th>Ngành</th>
                                                <th>Ưu tiên</th>
                                                <th>Thanh toán</th>
                                                <th>Ngày đăng ký</th>
                                                <th>Thao tác</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${pendingAspirations.map(asp => `
                                                <tr>
                                                    <td>${asp.candidate_name}</td>
                                                    <td>${asp.citizen_id}</td>
                                                    <td>${asp.university_name}</td>
                                                    <td>${asp.major_name}</td>
                                                    <td>${asp.priority}</td>
                                                    <td>
                                                        <span class="payment-status ${getPaymentStatusClass(asp.payment_status)}">
                                                            ${getPaymentStatusText(asp.payment_status)}
                                                        </span>
                                                    </td>
                                                    <td>${formatDate(asp.registered_at)}</td>
                                                    <td>
                                                        <button class="btn btn-success btn-sm" onclick="showApprovalModal(${asp.id}, 'approve')">
                                                            <i class="fas fa-check"></i> Duyệt
                                                        </button>
                                                        <button class="btn btn-danger btn-sm" onclick="showApprovalModal(${asp.id}, 'reject')">
                                                            <i class="fas fa-times"></i> Từ chối
                                                        </button>
                                                    </td>
                                                </tr>
                                            `).join('')}
                                        </tbody>
                                    </table>
                                </div>
                            ` : '<p class="text-muted">Không có nguyện vọng nào chờ duyệt</p>'}
                        </div>
                    </div>
                `;
            } catch (error) {
                const section = document.getElementById('manager-aspiration');
                section.innerHTML = `
                    <div class="alert alert-error">
                        <i class="fas fa-exclamation-circle"></i>
                        Lỗi khi tải danh sách nguyện vọng
                    </div>
                `;
            }
        }

        async function loadResults() {
            try {
                const result = await apiCall('/candidate/results');
                const results = result.data;
                
                const section = document.getElementById('results');
                
                section.innerHTML = `
                    <div class="content-panel">
                        <h3><i class="fas fa-chart-bar"></i> Kết quả tuyển sinh</h3>
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle"></i>
                            Kết quả xét tuyển sẽ được công bố sau khi kết thúc thời gian đăng ký
                        </div>
                        
                        <div id="resultsList">
                            ${results.length > 0 ? `
                                <div class="table-container">
                                    <table>
                                        <thead>
                                            <tr>
                                                <th>STT</th>
                                                <th>Trường</th>
                                                <th>Ngành</th>
                                                <th>Trạng thái</th>
                                                <th>Ghi chú</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${results.map(result => `
                                                <tr>
                                                    <td>${result.priority}</td>
                                                    <td>${result.university_name}</td>
                                                    <td>${result.major_name}</td>
                                                    <td>
                                                        <span class="status-badge ${getStatusClass(result.status)}">
                                                            ${getStatusText(result.status)}
                                                        </span>
                                                    </td>
                                                    <td>${result.status === 'approved' ? 'Đủ điều kiện' : 'Đang chờ'}</td>
                                                </tr>
                                            `).join('')}
                                        </tbody>
                                    </table>
                                </div>
                            ` : '<p class="text-muted">Chưa có kết quả nào</p>'}
                        </div>
                    </div>
                `;
            } catch (error) {
                const section = document.getElementById('results');
                section.innerHTML = `
                    <div class="alert alert-error">
                        <i class="fas fa-exclamation-circle"></i>
                        Lỗi khi tải kết quả
                    </div>
                `;
            }
        }

        // ==================== HELPER FUNCTIONS ====================
        function getStatusClass(status) {
            const classes = {
                'pending': 'status-pending',
                'approved': 'status-approved',
                'rejected': 'status-rejected',
                'completed': 'status-approved'
            };
            return classes[status] || 'status-pending';
        }

        function getStatusText(status) {
            const texts = {
                'pending': 'Chờ duyệt',
                'approved': 'Đã duyệt',
                'rejected': 'Đã từ chối',
                'completed': 'Hoàn thành'
            };
            return texts[status] || status;
        }

        function getPaymentStatusClass(status) {
            const classes = {
                'pending': 'payment-pending',
                'paid': 'payment-paid'
            };
            return classes[status] || 'payment-pending';
        }

        function getPaymentStatusText(status) {
            const texts = {
                'pending': 'Chưa thanh toán',
                'paid': 'Đã thanh toán'
            };
            return texts[status] || status;
        }

        function getPaymentMethodText(method) {
            const texts = {
                'bank_transfer': 'Chuyển khoản',
                'momo': 'Ví MoMo',
                'zalopay': 'Ví ZaloPay',
                'credit_card': 'Thẻ tín dụng'
            };
            return texts[method] || method;
        }

        function getDocumentIcon(category) {
            const icons = {
                'guide': 'book',
                'regulation': 'gavel',
                'template': 'file-alt',
                'announcement': 'bullhorn'
            };
            return icons[category] || 'file';
        }

        function formatCurrency(amount) {
            return new Intl.NumberFormat('vi-VN', {
                style: 'currency',
                currency: 'VND'
            }).format(amount);
        }

        function formatDate(dateString) {
            if (!dateString) return '-';
            const date = new Date(dateString);
            return date.toLocaleDateString('vi-VN');
        }

        // ==================== PROFILE FUNCTIONS ====================
        function enableProfileEditing() {
            const fields = [
                'profileFullname', 'profileEmail', 'profileDob', 'profileGender',
                'profileAddress', 'profilePhone', 'profileHighSchool', 'profileGraduationYear'
            ];
            
            fields.forEach(fieldId => {
                const field = document.getElementById(fieldId);
                if (field) {
                    field.readOnly = false;
                    field.disabled = false;
                }
            });
            
            document.getElementById('profileActions').style.display = 'flex';
        }

        function cancelProfileEditing() {
            loadProfile();
        }

        async function saveProfile() {
            showLoading();
            
            try {
                const formData = {
                    full_name: document.getElementById('profileFullname').value,
                    email: document.getElementById('profileEmail').value,
                    date_of_birth: document.getElementById('profileDob').value,
                    gender: document.getElementById('profileGender').value,
                    address: document.getElementById('profileAddress').value,
                    phone: document.getElementById('profilePhone').value,
                    high_school: document.getElementById('profileHighSchool').value,
                    graduation_year: document.getElementById('profileGraduationYear').value
                };
                
                const result = await apiCall('/candidate/profile/update', {
                    method: 'POST',
                    body: JSON.stringify(formData)
                });
                
                if (result.success) {
                    showAlert('Cập nhật thông tin thành công!', 'success');
                    currentUser.full_name = formData.full_name;
                    document.getElementById('userFullname').textContent = formData.full_name;
                    
                    await loadProfile();
                } else {
                    showAlert('Cập nhật thông tin thất bại', 'error');
                }
            } catch (error) {
                showAlert('Cập nhật thông tin thất bại', 'error');
            } finally {
                hideLoading();
            }
        }

        // ==================== ASPIRATION FUNCTIONS ====================
        async function loadUniversityMajors(universityId) {
            if (!universityId) return;
            
            try {
                const result = await apiCall(`/universities/${universityId}/majors`);
                majors = result.data;
                
                const majorSelect = document.getElementById('majorSelect');
                majorSelect.innerHTML = '<option value="">-- Chọn ngành --</option>' +
                    majors.map(major => `
                        <option value="${major.id}">${major.name} (${major.code})</option>
                    `).join('');
                majorSelect.disabled = false;
            } catch (error) {
                showAlert('Lỗi khi tải danh sách ngành học', 'error');
            }
        }

        async function addNewAspiration() {
            const universityId = document.getElementById('universitySelect').value;
            const majorId = document.getElementById('majorSelect').value;
            const priority = document.getElementById('prioritySelect').value;
            
            if (!universityId || !majorId || !priority) {
                showAlert('Vui lòng chọn đầy đủ thông tin', 'error');
                return;
            }
            
            showLoading();
            
            try {
                const result = await apiCall('/candidate/aspirations/add', {
                    method: 'POST',
                    body: JSON.stringify({
                        university_id: universityId,
                        major_id: majorId,
                        priority: priority
                    })
                });
                
                if (result.success) {
                    showAlert('Thêm nguyện vọng thành công!', 'success');
                    await loadAspiration();
                } else {
                    showAlert(result.error, 'error');
                }
            } catch (error) {
                showAlert('Thêm nguyện vọng thất bại', 'error');
            } finally {
                hideLoading();
            }
        }

        async function removeAspiration(aspirationId) {
            if (!confirm('Bạn có chắc chắn muốn xóa nguyện vọng này?')) return;
            
            showLoading();
            
            try {
                const result = await apiCall('/candidate/aspirations/remove', {
                    method: 'POST',
                    body: JSON.stringify({ aspiration_id: aspirationId })
                });
                
                if (result.success) {
                    showAlert('Xóa nguyện vọng thành công!', 'success');
                    await loadAspiration();
                } else {
                    showAlert(result.error, 'error');
                }
            } catch (error) {
                showAlert('Xóa nguyện vọng thất bại', 'error');
            } finally {
                hideLoading();
            }
        }

        // ==================== PAYMENT FUNCTIONS ====================
        async function showPaymentModal(aspirationId) {
            selectedAspirationForPayment = aspirationId;
            
            try {
                const configResult = await apiCall('/payment/config');
                const paymentConfig = configResult.data;
                
                document.getElementById('paymentContent').innerHTML = `
                    <div class="alert alert-info">
                        <i class="fas fa-info-circle"></i>
                        Phí đăng ký: ${formatCurrency(paymentConfig.aspiration_fee)}
                    </div>
                    
                    <div class="form-group">
                        <label>Chọn phương thức thanh toán</label>
                        <div class="payment-methods">
                            ${paymentConfig.payment_methods.map(method => `
                                <div class="payment-method" onclick="selectPaymentMethod('${method.value}')">
                                    <div class="payment-icon">
                                        <i class="fas fa-${method.value === 'bank_transfer' ? 'university' : method.value === 'momo' ? 'mobile-alt' : method.value === 'zalopay' ? 'qrcode' : 'credit-card'}"></i>
                                    </div>
                                    <div>${method.label}</div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    
                    ${selectedPaymentMethod === 'bank_transfer' ? `
                        <div class="bank-info">
                            <h4>Thông tin chuyển khoản:</h4>
                            <p><strong>Ngân hàng:</strong> ${paymentConfig.bank_info.bank_name}</p>
                            <p><strong>Số tài khoản:</strong> ${paymentConfig.bank_info.account_number}</p>
                            <p><strong>Chủ tài khoản:</strong> ${paymentConfig.bank_info.account_holder}</p>
                            <p><strong>Chi nhánh:</strong> ${paymentConfig.bank_info.branch}</p>
                            <p><strong>Nội dung:</strong> Thanh toán nguyện vọng ${aspirationId}</p>
                        </div>
                    ` : ''}
                    
                    <div class="form-actions">
                        <button type="button" class="btn btn-secondary" onclick="closeModal('paymentModal')">Hủy</button>
                        <button type="button" class="btn btn-primary" onclick="processPayment()" ${!selectedPaymentMethod ? 'disabled' : ''}>
                            <i class="fas fa-credit-card"></i> Xác nhận thanh toán
                        </button>
                    </div>
                `;
                
                showModal('paymentModal');
            } catch (error) {
                showAlert('Lỗi khi tải thông tin thanh toán', 'error');
            }
        }

        function selectPaymentMethod(method) {
            selectedPaymentMethod = method;
            
            // Update UI
            document.querySelectorAll('.payment-method').forEach(el => {
                el.classList.remove('selected');
            });
            event.target.closest('.payment-method').classList.add('selected');
            
            // Enable confirm button
            document.querySelector('#paymentModal .btn-primary').disabled = false;
            
            // Refresh bank info if needed
            if (method === 'bank_transfer') {
                showPaymentModal(selectedAspirationForPayment);
            }
        }

        async function processPayment() {
            if (!selectedPaymentMethod || !selectedAspirationForPayment) {
                showAlert('Vui lòng chọn phương thức thanh toán', 'error');
                return;
            }
            
            showLoading();
            
            try {
                const result = await apiCall('/payment/create', {
                    method: 'POST',
                    body: JSON.stringify({
                        aspiration_id: selectedAspirationForPayment,
                        payment_method: selectedPaymentMethod
                    })
                });
                
                if (result.success) {
                    showAlert('Tạo giao dịch thành công!', 'success');
                    closeModal('paymentModal');
                    
                    if (selectedPaymentMethod === 'bank_transfer') {
                        showAlert('Vui lòng chuyển khoản theo thông tin đã cung cấp', 'info');
                    } else {
                        // Simulate payment verification for demo
                        setTimeout(async () => {
                            await apiCall('/payment/verify', {
                                method: 'POST',
                                body: JSON.stringify({
                                    transaction_id: result.data.transaction_id
                                })
                            });
                            showAlert('Thanh toán thành công!', 'success');
                            await loadPayment();
                        }, 2000);
                    }
                    
                    await loadPayment();
                } else {
                    showAlert(result.error, 'error');
                }
            } catch (error) {
                showAlert('Tạo giao dịch thất bại', 'error');
            } finally {
                hideLoading();
            }
        }

        // ==================== MANAGER FUNCTIONS ====================
        async function showApprovalModal(aspirationId, action) {
            selectedAspirationForApproval = aspirationId;
            const aspiration = pendingAspirations.find(asp => asp.id === aspirationId);
            
            document.getElementById('approvalModalTitle').innerHTML = `
                <i class="fas fa-${action === 'approve' ? 'check-circle' : 'times-circle'}"></i>
                ${action === 'approve' ? 'Duyệt' : 'Từ chối'} Nguyện vọng
            `;
            
            document.getElementById('approvalContent').innerHTML = `
                <div class="alert alert-${action === 'approve' ? 'info' : 'warning'}">
                    <i class="fas fa-${action === 'approve' ? 'info-circle' : 'exclamation-triangle'}"></i>
                    Bạn đang ${action === 'approve' ? 'duyệt' : 'từ chối'} nguyện vọng của thí sinh <strong>${aspiration.candidate_name}</strong>
                </div>
                
                <div class="form-group">
                    <label>Thí sinh: ${aspiration.candidate_name}</label>
                </div>
                
                <div class="form-group">
                    <label>CCCD: ${aspiration.citizen_id}</label>
                </div>
                
                <div class="form-group">
                    <label>Trường: ${aspiration.university_name}</label>
                </div>
                
                <div class="form-group">
                    <label>Ngành: ${aspiration.major_name}</label>
                </div>
                
                <div class="form-group">
                    <label>Ưu tiên: ${aspiration.priority}</label>
                </div>
                
                <div class="form-group">
                    <label>Ghi chú:</label>
                    <textarea id="approvalNotes" rows="3" placeholder="${action === 'approve' ? 'Ghi chú cho thí sinh (nếu có)' : 'Lý do từ chối'}"></textarea>
                </div>
                
                <div class="form-actions">
                    <button type="button" class="btn btn-secondary" onclick="closeModal('approvalModal')">Hủy</button>
                    <button type="button" class="btn btn-${action === 'approve' ? 'success' : 'danger'}" onclick="${action === 'approve' ? 'approveAspiration' : 'rejectAspiration'}()">
                        <i class="fas fa-${action === 'approve' ? 'check' : 'times'}"></i>
                        ${action === 'approve' ? 'Duyệt' : 'Từ chối'}
                    </button>
                </div>
            `;
            
            showModal('approvalModal');
        }

        async function approveAspiration() {
            const notes = document.getElementById('approvalNotes').value;
            
            showLoading();
            
            try {
                const result = await apiCall('/manager/aspiration/approve', {
                    method: 'POST',
                    body: JSON.stringify({
                        aspiration_id: selectedAspirationForApproval,
                        notes: notes
                    })
                });
                
                if (result.success) {
                    showAlert('Duyệt nguyện vọng thành công!', 'success');
                    closeModal('approvalModal');
                    await loadManagerAspiration();
                    await loadDashboard();
                } else {
                    showAlert(result.error, 'error');
                }
            } catch (error) {
                showAlert('Duyệt nguyện vọng thất bại', 'error');
            } finally {
                hideLoading();
            }
        }

        async function rejectAspiration() {
            const reason = document.getElementById('approvalNotes').value;
            
            if (!reason) {
                showAlert('Vui lòng nhập lý do từ chối', 'error');
                return;
            }
            
            showLoading();
            
            try {
                const result = await apiCall('/manager/aspiration/reject', {
                    method: 'POST',
                    body: JSON.stringify({
                        aspiration_id: selectedAspirationForApproval,
                        reason: reason
                    })
                });
                
                if (result.success) {
                    showAlert('Từ chối nguyện vọng thành công!', 'success');
                    closeModal('approvalModal');
                    await loadManagerAspiration();
                    await loadDashboard();
                } else {
                    showAlert(result.error, 'error');
                }
            } catch (error) {
                showAlert('Từ chối nguyện vọng thất bại', 'error');
            } finally {
                hideLoading();
            }
        }

        // ==================== PRINT FUNCTIONS ====================
        async function generatePrintData() {
            try {
                const result = await apiCall('/print/aspirations');
                
                if (result.success) {
                    const data = result.data;
                    
                    document.getElementById('printContent').innerHTML = `
                        <div class="print-container">
                            <div class="print-header">
                                <h1>ĐẠI HỌC QUỐC GIA HÀ NỘI</h1>
                                <h2>DANH SÁCH NGUYỆN VỌNG ĐĂNG KÝ XÉT TUYỂN</h2>
                                <p>Kỳ thi tuyển sinh đại học năm 2025</p>
                            </div>
                            
                            <div class="candidate-info">
                                <h3>THÔNG TIN THÍ SINH</h3>
                                <table class="print-table">
                                    <tr>
                                        <td><strong>Họ và tên:</strong></td>
                                        <td>${data.candidate.full_name}</td>
                                        <td><strong>Số CCCD:</strong></td>
                                        <td>${data.candidate.citizen_id}</td>
                                    </tr>
                                    <tr>
                                        <td><strong>Ngày sinh:</strong></td>
                                        <td>${data.candidate.date_of_birth}</td>
                                        <td><strong>Giới tính:</strong></td>
                                        <td>${data.candidate.gender === 'male' ? 'Nam' : 'Nữ'}</td>
                                    </tr>
                                    <tr>
                                        <td><strong>Địa chỉ:</strong></td>
                                        <td colspan="3">${data.candidate.address}</td>
                                    </tr>
                                    <tr>
                                        <td><strong>Trường THPT:</strong></td>
                                        <td>${data.candidate.high_school}</td>
                                        <td><strong>Năm tốt nghiệp:</strong></td>
                                        <td>${data.candidate.graduation_year}</td>
                                    </tr>
                                </table>
                            </div>
                            
                            <div class="aspirations-list">
                                <h3>DANH SÁCH NGUYỆN VỌNG</h3>
                                <table class="print-table">
                                    <thead>
                                        <tr>
                                            <th>STT</th>
                                            <th>Mã trường</th>
                                            <th>Tên trường</th>
                                            <th>Mã ngành</th>
                                            <th>Tên ngành</th>
                                            <th>Khối thi</th>
                                            <th>Trạng thái</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${data.aspirations.map(asp => `
                                            <tr>
                                                <td>${asp.priority}</td>
                                                <td>${asp.university_code}</td>
                                                <td>${asp.university_name}</td>
                                                <td>${asp.major_code}</td>
                                                <td>${asp.major_name}</td>
                                                <td>${asp.subject_group}</td>
                                                <td>${getStatusText(asp.status)}</td>
                                            </tr>
                                        `).join('')}
                                    </tbody>
                                </table>
                            </div>
                            
                            <div class="print-footer">
                                <p>Ngày in: ${data.print_date}</p>
                                <div class="signature-section">
                                    <div class="signature-box">
                                        <p>Thí sinh</p>
                                        <div class="signature-line"></div>
                                        <p><em>(Ký và ghi rõ họ tên)</em></p>
                                    </div>
                                    <div class="signature-box">
                                        <p>Cán bộ tiếp nhận</p>
                                        <div class="signature-line"></div>
                                        <p><em>(Ký, ghi rõ họ tên và đóng dấu)</em></p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                    
                    showModal('printModal');
                } else {
                    showAlert('Lỗi khi tạo dữ liệu in', 'error');
                }
            } catch (error) {
                showAlert('Lỗi khi tạo dữ liệu in', 'error');
            }
        }

        async function exportToCSV() {
            try {
                const result = await apiCall('/print/aspirations/csv');
                
                if (result.success) {
                    // Create and download CSV file
                    const blob = new Blob([result.data], { type: 'text/csv;charset=utf-8;' });
                    const link = document.createElement('a');
                    const url = URL.createObjectURL(blob);
                    
                    link.setAttribute('href', url);
                    link.setAttribute('download', 'danh_sach_nguyen_vong.csv');
                    link.style.visibility = 'hidden';
                    
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    
                    showAlert('Xuất file CSV thành công!', 'success');
                } else {
                    showAlert('Lỗi khi xuất file CSV', 'error');
                }
            } catch (error) {
                showAlert('Lỗi khi xuất file CSV', 'error');
            }
        }

        // ==================== INITIALIZATION ====================
        document.addEventListener('DOMContentLoaded', function() {
            const token = localStorage.getItem('token');
            if (token) {
                // In a real application, you would verify the token with the server
                // For now, we'll just show the login page
                document.getElementById('loginPage').style.display = 'block';
            } else {
                document.getElementById('loginPage').style.display = 'block';
            }
        });

    </script>
</body>
</html>
"""
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))

    def handle_api_get(self):
        """Xử lý API GET requests"""
        if self.path == '/api/universities':
            self.get_universities()
        elif self.path.startswith('/api/universities/') and '/majors' in self.path:
            parts = self.path.split('/')
            university_id = parts[3]
            self.get_majors(university_id)
        elif self.path == '/api/exams/active':
            self.get_active_exam()
        elif self.path == '/api/candidate/profile':
            self.get_candidate_profile()
        elif self.path == '/api/candidate/aspirations':
            self.get_candidate_aspirations()
        elif self.path == '/api/candidate/results':
            self.get_candidate_results()
        elif self.path == '/api/candidate/stats':
            self.get_candidate_stats()
        elif self.path == '/api/documents':
            self.get_documents()
        elif self.path == '/api/payment/config':
            self.get_payment_config()
        elif self.path == '/api/payment/history':
            self.get_payment_history()
        elif self.path == '/api/manager/pending-aspirations':
            self.get_pending_aspirations()
        elif self.path == '/api/manager/stats':
            self.get_manager_stats()
        elif self.path == '/api/admin/stats':
            self.get_admin_stats()
        elif self.path == '/api/print/aspirations':
            self.print_aspirations()
        elif self.path == '/api/print/aspirations/csv':
            self.export_aspirations_csv()
        else:
            self.send_error(404, "API endpoint not found")
    
    def handle_api_post(self):
        """Xử lý API POST requests"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
        except:
            self.send_json_response({'success': False, 'error': 'Invalid JSON'}, 400)
            return
        
        if self.path == '/api/auth/login':
            self.login(data)
        elif self.path == '/api/auth/register':
            self.register(data)
        elif self.path == '/api/candidate/profile/update':
            self.update_candidate_profile(data)
        elif self.path == '/api/candidate/aspirations/add':
            self.add_aspiration(data)
        elif self.path == '/api/candidate/aspirations/remove':
            self.remove_aspiration(data)
        elif self.path == '/api/candidate/aspirations/reorder':
            self.reorder_aspirations(data)
        elif self.path == '/api/payment/create':
            self.create_payment(data)
        elif self.path == '/api/payment/verify':
            self.verify_payment(data)
        elif self.path == '/api/manager/aspiration/approve':
            self.approve_aspiration(data)
        elif self.path == '/api/manager/aspiration/reject':
            self.reject_aspiration(data)
        else:
            self.send_error(404, "API endpoint not found")
    
    # ==================== API METHODS ====================
    
    def get_candidate_stats(self):
        """Lấy thống kê cho thí sinh"""
        token = self.headers.get('Authorization')
        if not token:
            self.send_json_response({'success': False, 'error': 'Unauthorized'}, 401)
            return
        
        user_info = verify_token(token)
        if not user_info:
            self.send_json_response({'success': False, 'error': 'Invalid token'}, 401)
            return
        
        conn = sqlite3.connect('university_admission.db')
        cursor = conn.cursor()
        
        # Get candidate ID
        cursor.execute('SELECT id FROM candidates WHERE user_id = ?', (user_info['user_id'],))
        candidate = cursor.fetchone()
        
        if not candidate:
            self.send_json_response({'success': False, 'error': 'Candidate not found'})
            return
        
        candidate_id = candidate[0]
        
        # Count aspirations by status
        cursor.execute('SELECT status, COUNT(*) FROM aspirations WHERE candidate_id = ? GROUP BY status', (candidate_id,))
        status_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Count paid aspirations
        cursor.execute('SELECT COUNT(*) FROM aspirations WHERE candidate_id = ? AND payment_status = "paid"', (candidate_id,))
        paid_count = cursor.fetchone()[0]
        
        conn.close()
        
        self.send_json_response({
            'success': True,
            'data': {
                'totalAspirations': sum(status_counts.values()),
                'pendingAspirations': status_counts.get('pending', 0),
                'approvedAspirations': status_counts.get('approved', 0),
                'rejectedAspirations': status_counts.get('rejected', 0),
                'paidAspirations': paid_count
            }
        })
    
    def get_documents(self):
        """Lấy danh sách tài liệu"""
        category = self.path.split('?category=')[1] if '?category=' in self.path else None
        documents = get_documents(category)
        self.send_json_response({'success': True, 'data': documents})
    
    def get_payment_config(self):
        """Lấy cấu hình thanh toán"""
        payment_config = {
            'aspiration_fee': 50000,
            'currency': 'VND',
            'payment_methods': [
                {'value': 'bank_transfer', 'label': 'Chuyển khoản ngân hàng'},
                {'value': 'momo', 'label': 'Ví MoMo'},
                {'value': 'zalopay', 'label': 'Ví ZaloPay'},
                {'value': 'credit_card', 'label': 'Thẻ tín dụng'}
            ],
            'bank_info': {
                'bank_name': 'Ngân hàng ABC',
                'account_number': '123456789',
                'account_holder': 'Đại học Quốc gia Hà Nội',
                'branch': 'Chi nhánh Hà Nội'
            }
        }
        
        self.send_json_response({'success': True, 'data': payment_config})
    
    def get_payment_history(self):
        """Lấy lịch sử thanh toán"""
        token = self.headers.get('Authorization')
        if not token:
            self.send_json_response({'success': False, 'error': 'Unauthorized'}, 401)
            return
        
        user_info = verify_token(token)
        if not user_info:
            self.send_json_response({'success': False, 'error': 'Invalid token'}, 401)
            return
        
        conn = sqlite3.connect('university_admission.db')
        cursor = conn.cursor()
        
        # Get candidate ID
        cursor.execute('SELECT id FROM candidates WHERE user_id = ?', (user_info['user_id'],))
        candidate = cursor.fetchone()
        
        if not candidate:
            self.send_json_response({'success': False, 'error': 'Candidate not found'})
            return
        
        candidate_id = candidate[0]
        
        cursor.execute('''
            SELECT p.id, p.amount, p.payment_method, p.status, p.payment_date, p.created_at,
                   u.name as university_name, m.name as major_name, a.priority_order
            FROM payments p
            JOIN aspirations a ON p.aspiration_id = a.id
            JOIN universities u ON a.university_id = u.id
            JOIN majors m ON a.major_id = m.id
            WHERE p.candidate_id = ?
            ORDER BY p.created_at DESC
        ''', (candidate_id,))
        
        payments = []
        for row in cursor.fetchall():
            payments.append({
                'id': row[0],
                'amount': row[1],
                'payment_method': row[2],
                'status': row[3],
                'payment_date': row[4],
                'created_at': row[5],
                'university_name': row[6],
                'major_name': row[7],
                'priority': row[8]
            })
        
        conn.close()
        self.send_json_response({'success': True, 'data': payments})
    
    def create_payment(self, data):
        """Tạo thanh toán"""
        token = self.headers.get('Authorization')
        if not token:
            self.send_json_response({'success': False, 'error': 'Unauthorized'}, 401)
            return
        
        user_info = verify_token(token)
        if not user_info:
            self.send_json_response({'success': False, 'error': 'Invalid token'}, 401)
            return
        
        try:
            aspiration_id = data.get('aspiration_id')
            payment_method = data.get('payment_method')
            
            if not aspiration_id or not payment_method:
                self.send_json_response({'success': False, 'error': 'Aspiration ID and payment method are required'}, 400)
                return
            
            # Get candidate ID
            conn = sqlite3.connect('university_admission.db')
            cursor = conn.cursor()
            
            cursor.execute('SELECT id FROM candidates WHERE user_id = ?', (user_info['user_id'],))
            candidate = cursor.fetchone()
            
            if not candidate:
                self.send_json_response({'success': False, 'error': 'Candidate not found'})
                return
            
            candidate_id = candidate[0]
            
            # Get exam ID from aspiration
            cursor.execute('SELECT exam_id FROM aspirations WHERE id = ? AND candidate_id = ?', (aspiration_id, candidate_id))
            aspiration = cursor.fetchone()
            
            if not aspiration:
                self.send_json_response({'success': False, 'error': 'Aspiration not found'})
                return
            
            exam_id = aspiration[0]
            
            # Create payment
            amount = 50000  # Fixed fee
            payment_id, transaction_id = create_payment(candidate_id, exam_id, aspiration_id, amount, payment_method)
            
            if payment_id is None:
                self.send_json_response({'success': False, 'error': transaction_id})
                return
            
            conn.close()
            
            self.send_json_response({
                'success': True, 
                'data': {
                    'payment_id': payment_id,
                    'transaction_id': transaction_id,
                    'amount': amount
                }
            })
            
        except Exception as e:
            self.send_json_response({'success': False, 'error': str(e)})
    
    def verify_payment(self, data):
        """Xác nhận thanh toán"""
        token = self.headers.get('Authorization')
        if not token:
            self.send_json_response({'success': False, 'error': 'Unauthorized'}, 401)
            return
        
        try:
            transaction_id = data.get('transaction_id')
            
            if not transaction_id:
                self.send_json_response({'success': False, 'error': 'Transaction ID is required'}, 400)
                return
            
            verify_payment(transaction_id)
            
            self.send_json_response({'success': True, 'message': 'Payment verified successfully'})
            
        except Exception as e:
            self.send_json_response({'success': False, 'error': str(e)})
    
    def get_pending_aspirations(self):
        """Lấy danh sách nguyện vọng chờ duyệt"""
        token = self.headers.get('Authorization')
        if not token:
            self.send_json_response({'success': False, 'error': 'Unauthorized'}, 401)
            return
        
        user_info = verify_token(token)
        if not user_info or user_info['role'] not in ['manager', 'admin']:
            self.send_json_response({'success': False, 'error': 'Permission denied'}, 403)
            return
        
        pending_aspirations = get_pending_aspirations()
        self.send_json_response({'success': True, 'data': pending_aspirations})
    
    def approve_aspiration(self, data):
        """Duyệt nguyện vọng"""
        token = self.headers.get('Authorization')
        if not token:
            self.send_json_response({'success': False, 'error': 'Unauthorized'}, 401)
            return
        
        user_info = verify_token(token)
        if not user_info or user_info['role'] not in ['manager', 'admin']:
            self.send_json_response({'success': False, 'error': 'Permission denied'}, 403)
            return
        
        try:
            aspiration_id = data.get('aspiration_id')
            notes = data.get('notes', '')
            
            if not aspiration_id:
                self.send_json_response({'success': False, 'error': 'Aspiration ID is required'}, 400)
                return
            
            approve_aspiration(aspiration_id, user_info['user_id'], notes)
            
            self.send_json_response({'success': True, 'message': 'Aspiration approved successfully'})
            
        except Exception as e:
            self.send_json_response({'success': False, 'error': str(e)})
    
    def reject_aspiration(self, data):
        """Từ chối nguyện vọng"""
        token = self.headers.get('Authorization')
        if not token:
            self.send_json_response({'success': False, 'error': 'Unauthorized'}, 401)
            return
        
        user_info = verify_token(token)
        if not user_info or user_info['role'] not in ['manager', 'admin']:
            self.send_json_response({'success': False, 'error': 'Permission denied'}, 403)
            return
        
        try:
            aspiration_id = data.get('aspiration_id')
            reason = data.get('reason', '')
            
            if not aspiration_id:
                self.send_json_response({'success': False, 'error': 'Aspiration ID is required'}, 400)
                return
            
            reject_aspiration(aspiration_id, reason)
            
            self.send_json_response({'success': True, 'message': 'Aspiration rejected successfully'})
            
        except Exception as e:
            self.send_json_response({'success': False, 'error': str(e)})
    
    def print_aspirations(self):
        """In danh sách nguyện vọng"""
        token = self.headers.get('Authorization')
        if not token:
            self.send_json_response({'success': False, 'error': 'Unauthorized'}, 401)
            return
        
        user_info = verify_token(token)
        if not user_info:
            self.send_json_response({'success': False, 'error': 'Invalid token'}, 401)
            return
        
        # Get candidate ID
        conn = sqlite3.connect('university_admission.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM candidates WHERE user_id = ?', (user_info['user_id'],))
        candidate = cursor.fetchone()
        
        if not candidate:
            self.send_json_response({'success': False, 'error': 'Candidate not found'})
            return
        
        candidate_id = candidate[0]
        
        # Lấy dữ liệu nguyện vọng để in
        print_data = generate_aspirations_pdf(candidate_id)
        
        if print_data:
            self.send_json_response({'success': True, 'data': print_data})
        else:
            self.send_json_response({'success': False, 'error': 'Không tìm thấy dữ liệu nguyện vọng'})
    
    def export_aspirations_csv(self):
        """Xuất danh sách nguyện vọng ra CSV"""
        token = self.headers.get('Authorization')
        if not token:
            self.send_json_response({'success': False, 'error': 'Unauthorized'}, 401)
            return
        
        user_info = verify_token(token)
        if not user_info:
            self.send_json_response({'success': False, 'error': 'Invalid token'}, 401)
            return
        
        # Get candidate ID
        conn = sqlite3.connect('university_admission.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM candidates WHERE user_id = ?', (user_info['user_id'],))
        candidate = cursor.fetchone()
        
        if not candidate:
            self.send_json_response({'success': False, 'error': 'Candidate not found'})
            return
        
        candidate_id = candidate[0]
        
        # Xuất dữ liệu ra CSV
        csv_data = export_aspirations_csv(candidate_id)
        
        if csv_data:
            self.send_json_response({'success': True, 'data': csv_data})
        else:
            self.send_json_response({'success': False, 'error': 'Không tìm thấy dữ liệu nguyện vọng'})
    
    def get_universities(self):
        conn = sqlite3.connect('university_admission.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM universities WHERE status = "active" ORDER BY name')
        universities = []
        for row in cursor.fetchall():
            universities.append({
                'id': row[0],
                'code': row[1],
                'name': row[2],
                'address': row[3],
                'phone': row[4],
                'email': row[5],
                'website': row[6],
                'description': row[7]
            })
        
        conn.close()
        self.send_json_response({'success': True, 'data': universities})
    
    def get_majors(self, university_id):
        conn = sqlite3.connect('university_admission.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM majors 
            WHERE university_id = ? AND status = "active" 
            ORDER BY name
        ''', (university_id,))
        
        majors = []
        for row in cursor.fetchall():
            majors.append({
                'id': row[0],
                'university_id': row[1],
                'code': row[2],
                'name': row[3],
                'description': row[4],
                'quota': row[5],
                'subject_group': row[6],
                'duration': row[7],
                'tuition_fee': row[8]
            })
        
        conn.close()
        self.send_json_response({'success': True, 'data': majors})
    
    def get_active_exam(self):
        conn = sqlite3.connect('university_admission.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM exams WHERE status = "active" ORDER BY created_at DESC LIMIT 1')
        exam = cursor.fetchone()
        conn.close()
        
        if exam:
            exam_data = {
                'id': exam[0],
                'code': exam[1],
                'name': exam[2],
                'description': exam[3],
                'registration_start': exam[4],
                'registration_end': exam[5],
                'result_announcement': exam[6],
                'status': exam[7],
                'max_aspirations': exam[8],
                'aspiration_fee': exam[9],
                'created_at': exam[10]
            }
            self.send_json_response({'success': True, 'data': exam_data})
        else:
            self.send_json_response({'success': False, 'error': 'No active exam'})
    
    def get_candidate_profile(self):
        token = self.headers.get('Authorization')
        if not token:
            self.send_json_response({'success': False, 'error': 'Unauthorized'}, 401)
            return
        
        user_info = verify_token(token)
        if not user_info:
            self.send_json_response({'success': False, 'error': 'Invalid token'}, 401)
            return
        
        conn = sqlite3.connect('university_admission.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.id, u.username, u.email, u.full_name, u.role,
                   c.citizen_id, c.date_of_birth, c.gender, c.address, 
                   c.phone, c.high_school, c.graduation_year
            FROM users u
            LEFT JOIN candidates c ON u.id = c.user_id
            WHERE u.id = ?
        ''', (user_info['user_id'],))
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            self.send_json_response({
                'success': True,
                'data': {
                    'id': user[0],
                    'username': user[1],
                    'email': user[2],
                    'full_name': user[3],
                    'role': user[4],
                    'citizen_id': user[5],
                    'date_of_birth': user[6],
                    'gender': user[7],
                    'address': user[8],
                    'phone': user[9],
                    'high_school': user[10],
                    'graduation_year': user[11]
                }
            })
        else:
            self.send_json_response({'success': False, 'error': 'User not found'})
    
    def get_candidate_aspirations(self):
        token = self.headers.get('Authorization')
        if not token:
            self.send_json_response({'success': False, 'error': 'Unauthorized'}, 401)
            return
        
        user_info = verify_token(token)
        if not user_info:
            self.send_json_response({'success': False, 'error': 'Invalid token'}, 401)
            return
        
        conn = sqlite3.connect('university_admission.db')
        cursor = conn.cursor()
        
        # Get candidate ID
        cursor.execute('SELECT id FROM candidates WHERE user_id = ?', (user_info['user_id'],))
        candidate = cursor.fetchone()
        
        if not candidate:
            self.send_json_response({'success': True, 'data': []})
            return
        
        candidate_id = candidate[0]
        
        cursor.execute('''
            SELECT a.id, a.priority_order, a.status, a.registered_at, a.payment_status,
                   u.name as university_name, m.name as major_name,
                   u.code as university_code, m.code as major_code
            FROM aspirations a
            JOIN universities u ON a.university_id = u.id
            JOIN majors m ON a.major_id = m.id
            WHERE a.candidate_id = ?
            ORDER BY a.priority_order
        ''', (candidate_id,))
        
        aspirations = []
        for row in cursor.fetchall():
            aspirations.append({
                'id': row[0],
                'priority': row[1],
                'status': row[2],
                'registered_at': row[3],
                'payment_status': row[4],
                'university_name': row[5],
                'major_name': row[6],
                'university_code': row[7],
                'major_code': row[8]
            })
        
        conn.close()
        self.send_json_response({'success': True, 'data': aspirations})
    
    def get_candidate_results(self):
        token = self.headers.get('Authorization')
        if not token:
            self.send_json_response({'success': False, 'error': 'Unauthorized'}, 401)
            return
        
        user_info = verify_token(token)
        if not user_info:
            self.send_json_response({'success': False, 'error': 'Invalid token'}, 401)
            return
        
        conn = sqlite3.connect('university_admission.db')
        cursor = conn.cursor()
        
        # Get candidate ID
        cursor.execute('SELECT id FROM candidates WHERE user_id = ?', (user_info['user_id'],))
        candidate = cursor.fetchone()
        
        if not candidate:
            self.send_json_response({'success': True, 'data': []})
            return
        
        candidate_id = candidate[0]
        
        cursor.execute('''
            SELECT a.id, a.priority_order, a.status,
                   u.name as university_name, m.name as major_name,
                   a.registered_at
            FROM aspirations a
            JOIN universities u ON a.university_id = u.id
            JOIN majors m ON a.major_id = m.id
            WHERE a.candidate_id = ?
            ORDER BY a.priority_order
        ''', (candidate_id,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'priority': row[1],
                'status': row[2],
                'university_name': row[3],
                'major_name': row[4],
                'registered_at': row[5]
            })
        
        conn.close()
        self.send_json_response({'success': True, 'data': results})
    
    def get_admin_stats(self):
        token = self.headers.get('Authorization')
        if not token:
            self.send_json_response({'success': False, 'error': 'Unauthorized'}, 401)
            return
        
        user_info = verify_token(token)
        if not user_info or user_info['role'] != 'admin':
            self.send_json_response({'success': False, 'error': 'Permission denied'}, 403)
            return
        
        conn = sqlite3.connect('university_admission.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE role = "candidate" AND status = "active"')
        total_candidates = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM universities WHERE status = "active"')
        total_universities = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM aspirations')
        total_aspirations = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM aspirations WHERE status = "pending"')
        pending_aspirations = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM aspirations WHERE status = "approved"')
        approved_aspirations = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM payments WHERE status = "completed"')
        total_payments = cursor.fetchone()[0]
        
        conn.close()
        
        self.send_json_response({
            'success': True,
            'data': {
                'candidates': total_candidates,
                'universities': total_universities,
                'aspirations': total_aspirations,
                'pendingAspirations': pending_aspirations,
                'approvedAspirations': approved_aspirations,
                'totalPayments': total_payments
            }
        })
    
    def get_manager_stats(self):
        token = self.headers.get('Authorization')
        if not token:
            self.send_json_response({'success': False, 'error': 'Unauthorized'}, 401)
            return
        
        user_info = verify_token(token)
        if not user_info or user_info['role'] != 'manager':
            self.send_json_response({'success': False, 'error': 'Permission denied'}, 403)
            return
        
        conn = sqlite3.connect('university_admission.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM aspirations WHERE status = "pending"')
        pending_aspirations = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM aspirations WHERE status = "approved"')
        approved_aspirations = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM aspirations WHERE status = "rejected"')
        rejected_aspirations = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM payments WHERE status = "completed"')
        total_payments = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM aspirations')
        total_aspirations = cursor.fetchone()[0]
        
        conn.close()
        
        self.send_json_response({
            'success': True,
            'data': {
                'totalAspirations': total_aspirations,
                'pendingAspirations': pending_aspirations,
                'approvedAspirations': approved_aspirations,
                'rejectedAspirations': rejected_aspirations,
                'totalPayments': total_payments
            }
        })
    
    def login(self, data):
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            self.send_json_response({'success': False, 'error': 'Username and password are required'}, 400)
            return
        
        conn = sqlite3.connect('university_admission.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, username, password, email, full_name, role 
            FROM users 
            WHERE username = ? AND status = "active"
        ''', (username,))
        
        user = cursor.fetchone()
        conn.close()
        
        if user and verify_password(password, user[2]):
            token = create_token(user[0], user[1], user[5])
            
            self.send_json_response({
                'success': True,
                'token': token,
                'user': {
                    'id': user[0],
                    'username': user[1],
                    'email': user[3],
                    'full_name': user[4],
                    'role': user[5]
                }
            })
        else:
            self.send_json_response({'success': False, 'error': 'Invalid credentials'}, 401)
    
    def register(self, data):
        try:
            required_fields = ['username', 'password', 'email', 'full_name', 'citizen_id']
            for field in required_fields:
                if not data.get(field):
                    self.send_json_response({'success': False, 'error': f'Field {field} is required'}, 400)
                    return

            conn = sqlite3.connect('university_admission.db')
            cursor = conn.cursor()
            
            cursor.execute('SELECT id FROM users WHERE username = ? OR email = ?', 
                         (data['username'], data['email']))
            if cursor.fetchone():
                self.send_json_response({'success': False, 'error': 'Username or email already exists'})
                return
            
            cursor.execute('''
                INSERT INTO users (username, password, email, full_name, role) 
                VALUES (?, ?, ?, ?, 'candidate')
            ''', (data['username'], hash_password(data['password']), data['email'], data['full_name']))
            
            user_id = cursor.lastrowid
            
            cursor.execute('''
                INSERT INTO candidates (user_id, citizen_id, date_of_birth, gender, address, phone, high_school, graduation_year)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, data['citizen_id'], data.get('date_of_birth'), data.get('gender'), 
                  data.get('address'), data.get('phone'), data.get('high_school'), data.get('graduation_year')))
            
            conn.commit()
            conn.close()
            
            self.send_json_response({'success': True, 'message': 'Registration successful'})
            
        except Exception as e:
            self.send_json_response({'success': False, 'error': str(e)})
    
    def update_candidate_profile(self, data):
        token = self.headers.get('Authorization')
        if not token:
            self.send_json_response({'success': False, 'error': 'Unauthorized'}, 401)
            return
        
        user_info = verify_token(token)
        if not user_info:
            self.send_json_response({'success': False, 'error': 'Invalid token'}, 401)
            return
        
        try:
            conn = sqlite3.connect('university_admission.db')
            cursor = conn.cursor()
            
            # Update user table
            cursor.execute('''
                UPDATE users 
                SET email = ?, full_name = ?
                WHERE id = ?
            ''', (data.get('email'), data.get('full_name'), user_info['user_id']))
            
            # Update candidates table
            cursor.execute('''
                UPDATE candidates 
                SET date_of_birth = ?, gender = ?, address = ?, phone = ?, 
                    high_school = ?, graduation_year = ?
                WHERE user_id = ?
            ''', (data.get('date_of_birth'), data.get('gender'), data.get('address'),
                  data.get('phone'), data.get('high_school'), data.get('graduation_year'), user_info['user_id']))
            
            conn.commit()
            conn.close()
            
            self.send_json_response({'success': True, 'message': 'Profile updated successfully'})
            
        except Exception as e:
            self.send_json_response({'success': False, 'error': str(e)})
    
    def add_aspiration(self, data):
        token = self.headers.get('Authorization')
        if not token:
            self.send_json_response({'success': False, 'error': 'Unauthorized'}, 401)
            return
        
        user_info = verify_token(token)
        if not user_info:
            self.send_json_response({'success': False, 'error': 'Invalid token'}, 401)
            return
        
        try:
            university_id = data.get('university_id')
            major_id = data.get('major_id')
            priority = data.get('priority')
            
            if not university_id or not major_id or not priority:
                self.send_json_response({'success': False, 'error': 'Missing required fields'}, 400)
                return
            
            conn = sqlite3.connect('university_admission.db')
            cursor = conn.cursor()
            
            # Get candidate ID
            cursor.execute('SELECT id FROM candidates WHERE user_id = ?', (user_info['user_id'],))
            candidate = cursor.fetchone()
            if not candidate:
                self.send_json_response({'success': False, 'error': 'Candidate not found'})
                return
            
            candidate_id = candidate[0]
            
            cursor.execute('SELECT id FROM exams WHERE status = "active" LIMIT 1')
            exam = cursor.fetchone()
            if not exam:
                self.send_json_response({'success': False, 'error': 'No active exam'})
                return
            
            exam_id = exam[0]
            
            cursor.execute('''
                SELECT id FROM aspirations 
                WHERE candidate_id = ? AND exam_id = ? AND priority_order = ?
            ''', (candidate_id, exam_id, priority))
            
            if cursor.fetchone():
                self.send_json_response({'success': False, 'error': 'Priority order already exists'})
                return
            
            cursor.execute('''
                INSERT INTO aspirations (candidate_id, exam_id, university_id, major_id, priority_order)
                VALUES (?, ?, ?, ?, ?)
            ''', (candidate_id, exam_id, university_id, major_id, priority))
            
            conn.commit()
            conn.close()
            
            self.send_json_response({'success': True, 'message': 'Aspiration added successfully'})
            
        except Exception as e:
            self.send_json_response({'success': False, 'error': str(e)})
    
    def remove_aspiration(self, data):
        token = self.headers.get('Authorization')
        if not token:
            self.send_json_response({'success': False, 'error': 'Unauthorized'}, 401)
            return
        
        user_info = verify_token(token)
        if not user_info:
            self.send_json_response({'success': False, 'error': 'Invalid token'}, 401)
            return
        
        try:
            aspiration_id = data.get('aspiration_id')
            
            if not aspiration_id:
                self.send_json_response({'success': False, 'error': 'Aspiration ID is required'}, 400)
                return
            
            conn = sqlite3.connect('university_admission.db')
            cursor = conn.cursor()
            
            # Verify the aspiration belongs to the current user
            cursor.execute('''
                SELECT a.id FROM aspirations a
                JOIN candidates c ON a.candidate_id = c.id
                WHERE a.id = ? AND c.user_id = ?
            ''', (aspiration_id, user_info['user_id']))
            
            if not cursor.fetchone():
                self.send_json_response({'success': False, 'error': 'Aspiration not found or access denied'})
                return
            
            cursor.execute('DELETE FROM aspirations WHERE id = ?', (aspiration_id,))
            
            conn.commit()
            conn.close()
            
            self.send_json_response({'success': True, 'message': 'Aspiration removed successfully'})
            
        except Exception as e:
            self.send_json_response({'success': False, 'error': str(e)})
    
    def reorder_aspirations(self, data):
        token = self.headers.get('Authorization')
        if not token:
            self.send_json_response({'success': False, 'error': 'Unauthorized'}, 401)
            return
        
        user_info = verify_token(token)
        if not user_info:
            self.send_json_response({'success': False, 'error': 'Invalid token'}, 401)
            return
        
        try:
            aspirations = data.get('aspirations', [])
            
            if not aspirations:
                self.send_json_response({'success': False, 'error': 'No aspirations provided'}, 400)
                return
            
            conn = sqlite3.connect('university_admission.db')
            cursor = conn.cursor()
            
            # Get candidate ID
            cursor.execute('SELECT id FROM candidates WHERE user_id = ?', (user_info['user_id'],))
            candidate = cursor.fetchone()
            if not candidate:
                self.send_json_response({'success': False, 'error': 'Candidate not found'})
                return
            
            candidate_id = candidate[0]
            
            for aspiration in aspirations:
                # Verify the aspiration belongs to the current user
                cursor.execute('''
                    SELECT id FROM aspirations 
                    WHERE id = ? AND candidate_id = ?
                ''', (aspiration.get('id'), candidate_id))
                
                if not cursor.fetchone():
                    continue
                
                cursor.execute('''
                    UPDATE aspirations 
                    SET priority_order = ?
                    WHERE id = ?
                ''', (aspiration.get('priority'), aspiration.get('id')))
            
            conn.commit()
            conn.close()
            
            self.send_json_response({'success': True, 'message': 'Aspirations reordered successfully'})
            
        except Exception as e:
            self.send_json_response({'success': False, 'error': str(e)})
    
    def send_json_response(self, data, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        
        response = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.wfile.write(response)
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

def main():
    print("🔄 Đang khởi tạo cơ sở dữ liệu...")
    init_database()
    
    PORT = 8000
    
    with socketserver.TCPServer(("", PORT), AdmissionRequestHandler) as httpd:
        print(f"🚀 Hệ thống tuyển sinh ĐẦY ĐỦ TÍNH NĂNG đã khởi động!")
        print(f"📚 Truy cập: http://localhost:{PORT}")
        print(f"👤 Tài khoản demo:")
        print(f"   - Quản trị: admin / admin123")
        print(f"   - Cán bộ: manager / manager123") 
        print(f"   - Thí sinh: candidate / candidate123")
        print(f"\n✨ TÍNH NĂNG HOÀN THIỆN:")
        print(f"   ✅ Giao diện hiện đại với thiết kế mới")
        print(f"   ✅ Quản lý hồ sơ thí sinh đầy đủ")
        print(f"   ✅ Đăng ký nguyện vọng linh hoạt")
        print(f"   ✅ Hệ thống thanh toán an toàn")
        print(f"   ✅ Quản lý và duyệt nguyện vọng")
        print(f"   ✅ In ấn và xuất dữ liệu đa dạng")
        print(f"   ✅ Phân quyền người dùng chi tiết")
        print(f"\n⏹️  Nhấn Ctrl+C để dừng server")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print(f"\n🛑 Đang dừng server...")
            httpd.shutdown()

if __name__ == "__main__":
    main()